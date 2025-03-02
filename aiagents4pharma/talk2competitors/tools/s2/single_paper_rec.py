#!/usr/bin/env python3

"""
This tool is used to return recommendations for a single paper.
"""

import logging
from typing import Annotated, Any, Dict, Optional

import pandas as pd
import requests
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SinglePaperRecInput(BaseModel):
    """Input schema for single paper recommendation tool."""

    paper_id: str = Field(
        description="Semantic Scholar Paper ID to get recommendations for (40-character string)"
    )
    limit: int = Field(
        default=2,
        description="Maximum number of recommendations to return",
        ge=1,
        le=500,
    )
    year: Optional[str] = Field(
        default=None,
        description="Year range in format: YYYY for specific year, "
        "YYYY- for papers after year, -YYYY for papers before year, or YYYY:YYYY for range",
    )
    tool_call_id: Annotated[str, InjectedToolCallId]
    model_config = {"arbitrary_types_allowed": True}


@tool(args_schema=SinglePaperRecInput)
def get_single_paper_recommendations(
    paper_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    limit: int = 2,
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get paper recommendations based on a single paper.

    Args:
        paper_id (str): The Semantic Scholar Paper ID to get recommendations for.
        tool_call_id (Annotated[str, InjectedToolCallId]): The tool call ID.
        limit (int, optional): The maximum number of recommendations to return. Defaults to 2.
        year (str, optional): Year range for papers.
        Supports formats like "2024-", "-2024", "2024:2025". Defaults to None.

    Returns:
        Dict[str, Any]: The recommendations and related information.
    """
    logger.info("Starting single paper recommendations search.")

    endpoint = (
        f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
    )
    params = {
        "limit": min(limit, 500),  # Max 500 per API docs
        "fields": "paperId,title,abstract,year,authors,citationCount,url",
        "from": "all-cs",  # Using all-cs pool as specified in docs
    }

    # Add year parameter if provided
    if year:
        params["year"] = year

    response = requests.get(endpoint, params=params, timeout=10)
    data = response.json()
    papers = data.get("data", [])
    response = requests.get(endpoint, params=params, timeout=10)
    # print(f"API Response Status: {response.status_code}")
    logging.info(
        "API Response Status for recommendations of paper %s: %s",
        paper_id,
        response.status_code,
    )
    # print(f"Request params: {params}")
    logging.info("Request params: %s", params)

    data = response.json()
    recommendations = data.get("recommendedPapers", [])

    # Extract paper ID and title from recommendations
    filtered_papers = {
        paper["paperId"]: {
            "Title": paper.get("title", "N/A"),
            "Abstract": paper.get("abstract", "N/A"),
            "Year": paper.get("year", "N/A"),
            "Citation Count": paper.get("citationCount", "N/A"),
            "URL": paper.get("url", "N/A"),
            # "Publication Type": paper.get("publicationTypes", ["N/A"])[0]
            # if paper.get("publicationTypes")
            # else "N/A",
            # "Open Access PDF": paper.get("openAccessPdf", {}).get("url", "N/A")
            # if paper.get("openAccessPdf") is not None
            # else "N/A",
        }
        for paper in recommendations
        if paper.get("title") and paper.get("authors")
    }

    # Create a DataFrame for pretty printing
    df = pd.DataFrame(filtered_papers)

    # Format papers for state update
    papers = [
        f"Paper ID: {paper_id}\n"
        f"Title: {paper_data['Title']}\n"
        f"Abstract: {paper_data['Abstract']}\n"
        f"Year: {paper_data['Year']}\n"
        f"Citations: {paper_data['Citation Count']}\n"
        f"URL: {paper_data['URL']}\n"
        # f"Publication Type: {paper_data['Publication Type']}\n"
        # f"Open Access PDF: {paper_data['Open Access PDF']}"
        for paper_id, paper_data in filtered_papers.items()
    ]

    # Convert DataFrame to markdown table
    markdown_table = df.to_markdown(tablefmt="grid")
    logging.info("Search results: %s", papers)

    return Command(
        update={
            "papers": filtered_papers,  # Now sending the dictionary directly
            "messages": [
                ToolMessage(content=markdown_table, tool_call_id=tool_call_id)
            ],
        }
    )
