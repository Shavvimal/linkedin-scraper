from fastapi import HTTPException, Depends, APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from api.core.auth import verify_token
from api.utils.constants import SHARED
from typing import List, Optional
from api.models.find import SearchCompaniesInputs, SearchCompaniesInput
from api.find.apollo import fetch_companies, search_people, add_people_supabase, add_apollo_companies_supabase

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/find/companies")
async def search_companies_endpoint(
        background_tasks: BackgroundTasks,
        query: str
):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")

    try:
        search_agent = SHARED["search_companies"]
        supabase = SHARED["supabase_client"]
        company_list = search_agent.invoke(query)
        # Extracting the actual list of SearchCompaniesInput from tuples
        search_inputs = []
        for key, value in company_list:
            if key == "search_inputs":
                search_inputs.extend(value)

        companies = await fetch_companies(search_inputs) # Await the async function

        # Add new companies to the Supabase
        background_tasks.add_task(add_apollo_companies_supabase, supabase, companies)

        return JSONResponse(content=companies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/find/company")
async def search_company_endpoint(
        background_tasks: BackgroundTasks,
        name_query: str,
        organization_num_employees_ranges: Optional[List[str]] = None,
        organization_locations: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
):
    if not name_query:
        raise HTTPException(status_code=400, detail="Query parameter cannot be empty.")

    try:

        supabase = SHARED["supabase_client"]

        search_inputs = [SearchCompaniesInput(
            q_organization_name=name_query,
            organization_num_employees_ranges=organization_num_employees_ranges,
            organization_locations=organization_locations,
            q_organization_keyword_tags=keywords
        )]
        companies = await fetch_companies(search_inputs) # Await the async function
        print(companies)
        # Add new companies to the Supabase
        background_tasks.add_task(add_apollo_companies_supabase, supabase, companies)

        return JSONResponse(content=companies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find/people")
async def search_people_endpoint(
        background_tasks: BackgroundTasks,
        person_titles: List[str],
        q_keywords: Optional[str] = None,
        person_locations: Optional[List[str]] = None,
        person_seniorities: Optional[List[str]] = None,
        organization_locations: Optional[List[str]] = None,
        organization_ids: Optional[List[str]] = None,
        organization_num_employees_ranges: Optional[List[str]] = None,
        per_page: Optional[int] = 3
):
    try:
        supabase = SHARED["supabase_client"]
        people_data = await search_people(
            person_titles=person_titles,
            q_keywords=q_keywords,
            person_locations=person_locations,
            person_seniorities=person_seniorities,
            organization_locations=organization_locations,
            organization_ids=organization_ids,
            organization_num_employees_ranges=organization_num_employees_ranges,
            per_page=per_page
        )

        # Add data to Supabase in the background to avoid delaying response time
        add_people_supabase(supabase, people_data)

        return JSONResponse(content=people_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    from api.find.search_agent import SearchAgent
    import os
    from dotenv import load_dotenv
    from supabase import create_client, Client
    import asyncio
    from api.utils.logger import setup_logger

    load_dotenv()
    setup_logger()

    SHARED["search_companies"] = SearchAgent("companies")

    # The unique Supabase URL which is supplied when you create a new project in your project dashboard.
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    # The unique Supabase Key which is supplied when you create a new project in your project dashboard.
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    SHARED["supabase_client"] = supabase

    # Test search_companies_endpoint

    async def main ():
        query = "Top Manufacturing companies in Virginia"
        background_tasks = BackgroundTasks()
        res = await search_companies_endpoint(background_tasks, query)
        print(res)

    async def main2 ():
        name_query = "YC"
        keywords = ["Venture Capital"]
        background_tasks = BackgroundTasks()
        res = await search_company_endpoint(background_tasks, name_query, keywords=keywords)
        print(res)

    asyncio.run(main2())