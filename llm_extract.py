import os
import json
from typing import Optional, TypedDict, List
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.llms import Anyscale
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser

# Define the schema for a football match using Pydantic BaseModel.
# Each field represents an attribute to be extracted from the raw match data.
class Match(BaseModel):
    """Information about a match between Hometeam and Awayteam."""
    matchday_order: Optional[int] = Field(default=None, description="The order of the matchday in the season, appears at the beginning of the line.")
    home_team: Optional[str] = Field(default=None, description="The name of the team that appears first.")
    home_team_position: Optional[int] = Field(default=None, description="The number in round brackets before the home team name, indicating the home team's rank.")
    home_team_score: Optional[int] = Field(default=None, description="The number immediately after the home team name, indicating the home team's score.")
    away_team: Optional[str] = Field(default=None, description="The name of the team that appears second.")
    away_team_position: Optional[int] = Field(default=None, description="The number in round brackets after the away team name, indicating the away team's rank.")
    away_team_score: Optional[int] = Field(default=None, description="The number before the away team name, indicating the away team's score.")
    home_team_starting_lineup: Optional[str] = Field(default=None, description="Home team lineup, appears first. Only include the numbers.")
    away_team_starting_lineup: Optional[str] = Field(default=None, description="Away team lineup, appears second. Only include the numbers.")
    comunity_prediction_home_team_win: Optional[float] = Field(default=None, description="First number in the community prediction, home team win percentage.")
    comunity_prediction_draw: Optional[float] = Field(default=None, description="Second number in the community prediction, draw percentage.")
    comunity_prediction_away_team_win: Optional[float] = Field(default=None, description="Third number in the community prediction, away team win percentage.")
    date: Optional[str] = Field(default=None, description="Date of the match in dd/mm/yyyy format.")
    referee: Optional[str] = Field(default=None, description="Name of the referee.")

# Define an Example type for few-shot learning.
# Each example contains a query (raw match text) and the expected output (Match object).
class Example(TypedDict):
    query: str
    output: Match

def convert_example_into_message(example: Example):
    """
    Convert an Example object into a list of messages for the prompt template.
    This helps the LLM understand the expected input-output format.
    """
    query = example["query"]
    output = example["output"]
    # Helper function to format values for JSON output
    def val(x): return "null" if x is None else (f'"{x}"' if isinstance(x, str) else x)
    # Build the expected AI output in JSON format
    ai_output = (
        f'"matchday_order": {val(output.matchday_order)},\n'
        f'"home_team": {val(output.home_team)},\n'
        f'"home_team_position": {val(output.home_team_position)},\n'
        f'"home_team_score": {val(output.home_team_score)},\n'
        f'"away_team": {val(output.away_team)},\n'
        f'"away_team_position": {val(output.away_team_position)},\n'
        f'"away_team_score": {val(output.away_team_score)},\n'
        f'"home_team_starting_lineup": {val(output.home_team_starting_lineup)},\n'
        f'"away_team_starting_lineup": {val(output.away_team_starting_lineup)},\n'
        f'"comunity_prediction_home_team_win": {val(output.comunity_prediction_home_team_win)},\n'
        f'"comunity_prediction_draw": {val(output.comunity_prediction_draw)},\n'
        f'"comunity_prediction_away_team_win": {val(output.comunity_prediction_away_team_win)},\n'
        f'"date": {val(output.date)},\n'
        f'"referee": {val(output.referee)}'
    )
    # Wrap the output in a code block for the LLM to follow the format
    ai_output = f"\n```json\n{{{ai_output}}}\n```"
    # Return as a list of (role, content) tuples for the prompt
    return [("user", query), ("ai", ai_output)]

def build_chain(anyscale_api_key: str, anyscale_model_name: str, temperature: float = 0.0):
    """
    Build a Langchain chain for extraction:
    - Sets up the LLM (Anyscale)
    - Sets up the output parser (PydanticOutputParser)
    - Sets up the prompt template with system instructions and example placeholders
    Returns a chain: prompt | llm | parser
    """
    os.environ["ANYSCALE_API_KEY"] = anyscale_api_key
    llm = Anyscale(model_name=anyscale_model_name, temperature=temperature)
    parser = PydanticOutputParser(pydantic_object=Match)
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert extraction algorithm in a football match. "
            "Only extract relevant information from the text. "
            "Return null for the attribute's values you can't find. "
            "Don't make up the information if you can't find it. "
            "Answer the user query. NO NEED TO PRINT 'AI:' IN OUTPUT. Wrap the output in ```json tag\n{format_instructions}"
        ),
        MessagesPlaceholder("example"),
        ("user", "{query}")
    ]).partial(format_instructions=parser.get_format_instructions())
    # Return the composed chain
    return prompt | llm | parser

def extract_matches(raw_data: List[str], example_set: List[Example], chain, max_retry: int = 2):
    """
    Extract structured match data from a list of raw match strings using the provided chain.
    - raw_data: list of raw match text strings
    - example_set: list of Example objects for few-shot learning
    - chain: the Langchain chain (prompt | llm | parser)
    - max_retry: number of retries if extraction fails
    Returns a list of Match objects (or None if extraction failed).
    """
    # Prepare the example messages for the prompt
    messages = []
    for example in example_set:
        messages.extend(convert_example_into_message(example))
    results = []
    # Iterate over each raw match string
    for i, query in enumerate(raw_data):
        retry = 0
        while retry <= max_retry:
            try:
                # Invoke the chain with the query and example messages
                result = chain.invoke({"query": query, "example": messages})
                results.append(result)
                break
            except Exception as e:
                retry += 1
                if retry > max_retry:
                    # If all retries fail, append None
                    results.append(None)
    return results


