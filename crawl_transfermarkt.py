import os
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

# Constants for Selenium waits and retries
WAIT_TIME = 5
MAX_ERROR_TIMES = 5

# Chrome options: disable image loading for faster scraping
DEFAULT_CHROME_OPTIONS = webdriver.ChromeOptions()
PREFS = {"profile.managed_default_content_settings.images": 2}
DEFAULT_CHROME_OPTIONS.add_experimental_option("prefs", PREFS)

# URL components for Transfermarkt navigation
HOME_PAGE = 'https://www.transfermarkt.com'
MID_URL = 'spieltag/wettbewerb'
LAST_URL = 'saison_id'

# CSS selectors and element IDs for Transfermarkt site
TransfermarktWeb = {
    'id_popup_accept': 'sp_message_iframe_953358',
    'css_button_accept': 'button[title="Accept & continue"]',
    'css_quick_select_bar': 'tm-quick-select-bar.hydrated',
    'css_quick_select_in_shadow_root': 'tm-quick-select.hydrated',
    'css_list_tm_quick_select_item': 'div.selector-dropdown > ul > tm-quick-select-item.hydrated',
    'css_forward_button': 'a.forward-button',
    'css_button_show': 'tr > td > input[class="small button right"]',
    'css_box_table_select': 'table.auflistung > tbody > tr div.inline-select > div',
    'css_list_li_select': 'ul.chzn-results li',
    'css_matchday_overviews_boxs': 'div.box[style="border-top: 0 !important;"]',
    'css_matchday_infor_overview': 'table > tbody',
    'css_link_matchday_report': 'div.footer > a.liveLink',
    'css_lineup': 'main > div.row > div[class="large-12 columns"] > div.box > div.large-6',
    'css_lineup_name_team': 'a[class="sb-vereinslink"]',
    'css_starting_lineup': 'div.row div.aufstellung-unterueberschrift'
}

def accept_cookies(driver):
    """
    Accept the cookie popup that appears when first visiting the site.
    Switches to the iframe and clicks the accept button.
    """
    time.sleep(3)
    try:
        while len(driver.find_elements(By.ID, TransfermarktWeb['id_popup_accept'])) > 0:
            driver.switch_to.frame(TransfermarktWeb['id_popup_accept'])
            button_accept = driver.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_button_accept'])
            button_accept.click()
            time.sleep(3)
            driver.switch_to.default_content()
    except Exception:
        raise ValueError("Can't close pop-up iframe to accept cookies")

def scroll_page_to_element(driver, element: WebElement):
    """
    Scroll the page to bring the given element into the center of the viewport.
    """
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    except Exception:
        raise ValueError('Scroll page to element error!')

def get_list_select_boxs(driver):
    """
    Get the list of quick select boxes (country, league, etc.) from the navigation bar.
    """
    bar = driver.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_quick_select_bar'])
    return bar.shadow_root.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_quick_select_in_shadow_root'])

def get_list_items_quick_select(contain_element):
    """
    Get the list of options in a quick select box.
    """
    if contain_element.get_attribute('dropdown-visible') is None:
        contain_element.click()
    return contain_element.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_list_tm_quick_select_item'])

def select_item_quick_select_by_content(contain_element, content):
    """
    Select an option in a quick select box by its text content.
    """
    items = get_list_items_quick_select(contain_element)
    if contain_element.get_attribute('dropdown-visible') is None:
        items.click()
    for item in items:
        if content == item.text:
            item.click()
            break
    return contain_element.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_forward_button']).get_attribute('href')

def select_item_first(contain_element):
    """
    Select the first option in a quick select box.
    """
    items = get_list_items_quick_select(contain_element)
    if contain_element.get_attribute('dropdown-visible') is None:
        items.click()
    items[0].click()
    return contain_element.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_forward_button']).get_attribute('href')

def get_url_to_matchday_table(driver, name_country, wait=WAIT_TIME, max_error_times=MAX_ERROR_TIMES):
    """
    Build the URL to the matchday table after selecting the country and league.
    Retries if navigation fails.
    """
    error_times = 0
    while error_times < max_error_times:
        try:
            quick_select_boxs = get_list_select_boxs(driver)
            select_item_quick_select_by_content(quick_select_boxs[0], name_country)
            driver.implicitly_wait(wait)
            url = select_item_first(quick_select_boxs[1])
            url = url.split('/')
            return "/".join([HOME_PAGE, url[3], MID_URL, url[6], LAST_URL])
        except Exception:
            error_times += 1
            driver.refresh()
            driver.implicitly_wait(wait)
    raise ValueError('Get url to matchday table failed!')

def to_matchday_table(driver, url, wait=WAIT_TIME):
    """
    Navigate the browser to the matchday table page.
    """
    driver.get(url)
    driver.implicitly_wait(wait)

def get_filter_select_boxs(driver, max_error_times=MAX_ERROR_TIMES):
    """
    Get the filter select boxes for season and matchday.
    """
    error_times = 0
    while error_times < max_error_times:
        try:
            return driver.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_box_table_select'])
        except Exception:
            error_times += 1
            driver.refresh()

def submit_show(driver, wait=WAIT_TIME):
    """
    Click the 'Show' button to confirm filter selections.
    """
    try:
        driver.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_button_show']).click()
        driver.implicitly_wait(wait)
    except Exception:
        raise ValueError('Submit show error!')

def get_list_items_filter_select(contain_element):
    """
    Get the list of options in a filter select box (season, matchday).
    """
    if 'chzn-with-drop' not in contain_element.get_attribute('class'):
        contain_element.click()
    return contain_element.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_list_li_select'])

def select_item_filter_select_by_content(contain_element, content):
    """
    Select an option in a filter select box by its text content.
    """
    items = get_list_items_filter_select(contain_element)
    if 'chzn-with-drop' not in contain_element.get_attribute('class'):
        contain_element.click()
    for item in items:
        if content == item.text:
            item.click()
            return
    contain_element.click()

def get_list_overviews_boxs(driver, wait=WAIT_TIME, max_error_times=MAX_ERROR_TIMES):
    """
    Get the list of match overview boxes for a matchday.
    """
    error_times = 0
    while error_times < max_error_times:
        try:
            return driver.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_matchday_overviews_boxs'])
        except Exception:
            error_times += 1
            driver.refresh()
            driver.implicitly_wait(wait)
    raise ValueError('Get overviews boxs error!')

def get_urls_to_match_report(list_overviews_boxs):
    """
    Get the URLs to the match report pages for each match in a matchday.
    """
    urls = []
    for box in list_overviews_boxs:
        url = box.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_link_matchday_report']).get_attribute('href')
        urls.append(url)
    return urls

def get_overviews_in_matchday(list_overviews_boxs):
    """
    Get the overview information (team names, scores, etc.) for each match in a matchday.
    """
    overviews = []
    for ovb in list_overviews_boxs:
        content_element = ovb.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_matchday_infor_overview']).text
        overviews.append(content_element)
    return overviews

def get_lineups_in_matchday(driver, list_urls, wait=WAIT_TIME, max_error_times=MAX_ERROR_TIMES):
    """
    Get the starting lineup information for each team in each match in a matchday.
    """
    error_time = 0
    while error_time < max_error_times:
        try:
            lineup_infors = []
            for url in list_urls:
                driver.get(url)
                lineup_element = driver.find_elements(By.CSS_SELECTOR, TransfermarktWeb['css_lineup'])
                for lue in lineup_element:
                    lineup = ''
                    try:
                        lineup += lue.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_lineup_name_team']).text
                    except Exception:
                        lineup += 'None'
                    lineup += '\n'
                    try:
                        lineup += lue.find_element(By.CSS_SELECTOR, TransfermarktWeb['css_starting_lineup']).text
                    except Exception:
                        lineup += 'None'
                    lineup += '\n'
                    lineup_infors.append(lineup)
                driver.back()
                driver.implicitly_wait(wait)
            return lineup_infors
        except Exception:
            error_time += 1
            driver.refresh()
            driver.implicitly_wait(wait)
            return ['None/nNone/n', 'None/nNone/n']

def get_matchday_infor(driver):
    """
    Get all match information (overview + lineups) for a matchday.
    """
    list_overviews_boxs = get_list_overviews_boxs(driver)
    overviews_content = get_overviews_in_matchday(list_overviews_boxs)
    list_urls = get_urls_to_match_report(list_overviews_boxs)
    lineup_infors = get_lineups_in_matchday(driver, list_urls)
    result = []
    for i in range(len(overviews_content)):
        result.append(overviews_content[i] + lineup_infors[2*i] + lineup_infors[2*i + 1])
    return result

def write_to_json(file_name, data):
    """
    Write the collected data to a JSON file.
    If the file exists, update it; otherwise, create a new file.
    """
    if os.path.exists(file_name):
        with open(file_name, 'r') as f:
            old_data = json.load(f)
    else:
        old_data = {}
    old_data.update(data)
    with open(file_name, 'w') as f:
        json.dump(old_data, f, indent=4)

def crawl_country(country_name, file_output, except_seasons=None, nseasons=5, wait=WAIT_TIME, max_error_times=MAX_ERROR_TIMES):
    """
    Main function to crawl match data for a given country.
    - country_name: Name of the country (e.g., 'France')
    - file_output: Output JSON file name
    - except_seasons: List of seasons to skip (e.g., ['24/25', '2024'])
    - nseasons: Number of seasons to crawl
    """
    except_seasons = except_seasons or []
    driver = webdriver.Chrome(options=DEFAULT_CHROME_OPTIONS)
    driver.get(HOME_PAGE)
    accept_cookies(driver)
    url = get_url_to_matchday_table(driver, country_name, wait, max_error_times)
    to_matchday_table(driver, url, wait)
    filter_select_boxs = get_filter_select_boxs(driver)
    # Implement logic to select seasons, matchdays, and extract data as needed
    # ...
    driver.quit()

# Example usage (to be run in a main guard or another script):
# crawl_country('France', 'france.json', except_seasons=['24/25', '2024'], nseasons=5)
