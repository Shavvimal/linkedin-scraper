import os
import asyncio
from typing import Optional, List
from supabase import Client
from logging import getLogger
from pprint import pprint
from dotenv import load_dotenv
import aiohttp


from api.models.find import SearchCompaniesInput, SearchCompaniesInputs

load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
logger = getLogger("API")

async def search_people(
    person_titles: Optional[List[str]] = None,
    q_keywords: Optional[str] = None,
    person_locations: Optional[List[str]] = None,
    person_seniorities: Optional[List[str]] = None,
    contact_email_status: Optional[List[str]] = None,
    q_organization_domains: Optional[str] = None,
    organization_locations: Optional[List[str]] = None,
    organization_ids: Optional[List[str]] = None,
    organization_num_employees_ranges: Optional[List[str]] = None,
    page: Optional[int] = 1,
    per_page: Optional[int] = 100
):
    """
    Search for people
    :param person_titles: An array of the person's title. Apollo will return results matching ANY of the titles passed in e.g., ["sales director", "engineer manager"]
    :param q_keywords: A string of words over which we want to filter the results e.g., "Tim"
    :param person_locations: An array of strings denoting allowed locations of the person e.g., ["California, US", "Minnesota, US"]
    :param person_seniorities: An array of strings denoting the seniorities or levels e.g., ["senior", "manager"]
    :param contact_email_status: An array of strings to look for people having a set of email statuses e.g., ["verified", "guessed", "unavailable", "bounced", "pending_manual_fulfillment"]
    :param q_organization_domains: An array of the company domains to search for, joined by the new line character. e.g., "google.com\nfacebook.com"
    :param organization_locations: An array of strings denoting allowed locations of organization headquarters of the person e.g., ["California, US", "Minnesota, US"]
    :param organization_ids: An array of organization ids obtained from companies-search e.g., ["63ff0bc1ff57ba0001e7eXXX"]
    :param organization_num_employees_ranges: An array of intervals to include people belonging in an organization having number of employees in a range e.g., ["1,10", "101,200"]
    :param page: An integer that allows you to paginate through the results e.g., 1
    :param per_page: An integer to load per_page results on a page. Should be in inclusive range [1, 100]  e.g., 10
    :return: List of people
    """
    url = "https://api.apollo.io/v1/mixed_people/search"

    data = {key: value for key, value in {
        "person_titles": person_titles,
        "q_keywords": q_keywords,
        "person_locations": person_locations,
        "person_seniorities": person_seniorities,
        "contact_email_status": contact_email_status,
        "q_organization_domains": q_organization_domains,
        "organization_locations": organization_locations,
        "organization_ids": organization_ids,
        "organization_num_employees_ranges": organization_num_employees_ranges,
        "page": page,
        "per_page": per_page
    }.items() if value is not None}

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        'X-Api-Key': APOLLO_API_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                resp_data = await resp.json()
    except Exception as e:
        logger.error(f"Error occurred while searching people: {e}")
        return []

    people = []

    if "people" in resp_data:
        for person in resp_data['people']:
            employment_history = [
                {
                    'start_date': employment.get('start_date'),
                    'end_date': employment.get('end_date'),
                    'current': employment.get('current'),
                    'degree': employment.get('degree'),
                    'description': employment.get('description'),
                    'organization_id': employment.get('organization_id'),
                    'organization_name': employment.get('organization_name'),
                    'title': employment.get('title'),
                    'created_at': employment.get('created_at')
                }
                for employment in person.get('employment_history', [])
            ]
            # Reverse the list so that the most recent employment is first
            organization = person.get('organization')
            organization_data = {
                'linkedin_url': organization.get('linkedin_url') if organization else None,
                'name': organization.get('name') if organization else None
            }

            people.append({
                'person_id': person.get('id'),
                'first_name': person.get('first_name'),
                'last_name': person.get('last_name'),
                'title': person.get('title'),
                'headline': person.get('headline'),
                'seniority': person.get('seniority'),
                'departments': person.get('departments'), # (list)
                'subdepartments': person.get('subdepartments'), # (list)
                'functions': person.get('functions'), # (list)
                'state': person.get('state'),
                'city': person.get('city'),
                'country': person.get('country'),
                'email': person.get('email'),
                'linkedin_url': person.get('linkedin_url'),
                'github_url': person.get('github_url'),
                'photo_url': person.get('photo_url'),
                'organization': organization_data,
                'employment_history': employment_history
            })

    return people


def add_people_supabase(supabase: Client, people: List[dict]):
    """
    Add people data to Supabase.
    """
    try:
        supabase.table("people").upsert(people, on_conflict="person_id").execute()
    except Exception as e:
        logger.error(f"Error occurred while adding people to Supabase: {e}")
    return True

async def search_companies(
    page: Optional[int] = 1,
    per_page: Optional[int] = 10,
    organization_num_employees_ranges: Optional[List[str]] = None,
    organization_locations: Optional[List[str]] = None,
    organization_not_locations: Optional[List[str]] = None,
    q_organization_keyword_tags: Optional[List[str]] = None,
    q_organization_name: Optional[str] = None
) -> Optional[dict]:
    """
    Search for companies
    :param page: An integer that allows you to paginate through the results e.g., 1
    :param per_page: An integer to load per_page results on a page. Should be in inclusive range [1, 100]  e.g., 10
    :param organization_num_employees_ranges: An array of intervals to include organizations having a number of employees in a range e.g., ["1,100", "1,1000"]
    :param organization_locations: An array of strings denoting allowed locations of organization headquarters e.g., ["United States"]
    :param organization_not_locations: An array of strings denoting un-allowed locations of organization headquarters e.g., ["India"]
    :param q_organization_keyword_tags: An array of strings denoting the keywords an organization should be associated with e.g., ["sales strategy", "lead"]
    :param q_organization_name: A string representing the name of the organization we want to filter e.g., "Apollo.io"
    """

    url = "https://api.apollo.io/api/v1/mixed_companies/search"

    data = {key: value for key, value in {
        "page": page,
        "per_page": per_page,
        "organization_num_employees_ranges": organization_num_employees_ranges,
        "organization_locations": organization_locations,
        "organization_not_locations": organization_not_locations,
        "q_organization_keyword_tags": q_organization_keyword_tags,
        "q_organization_name": q_organization_name
    }.items() if value is not None}

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        'X-Api-Key': APOLLO_API_KEY
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                resp_data = await response.json()
    except Exception as e:
        logger.error(f"Error occurred while searching companies: {e}")
        return None

    if "organizations" in resp_data and resp_data['organizations']:
        return {
            'company_id': resp_data['organizations'][0].get('id'),
            'name': resp_data['organizations'][0].get('name'),
            'founded_year': resp_data['organizations'][0].get('founded_year'),
            'linkedin_url': resp_data['organizations'][0].get('linkedin_url'),
            'website_url': resp_data['organizations'][0].get('website_url')
        }

    return None


def add_apollo_companies_supabase(supabase: Client, companies: List[dict]):
    """
    Add companies data to Supabase.
    """
    try:
        supabase.table("companies").upsert(companies, on_conflict="company_id").execute()
    except Exception as e:
        logger.error(f"Error occurred while adding companies to Supabase: {e}")
    return True

async def fetch_companies(organizations: List[SearchCompaniesInput]) -> List[dict]:
    """
    Fetch companies concurrently
    """
    companies = []

    async def fetch_company(input_data: SearchCompaniesInput):
        try:
            response = await search_companies(
                organization_num_employees_ranges=input_data.organization_num_employees_ranges,
                organization_locations=input_data.organization_locations,
                organization_not_locations=input_data.organization_not_locations,
                q_organization_keyword_tags=input_data.q_organization_keyword_tags,
                q_organization_name=input_data.q_organization_name
            )
            if response:
                companies.append(response)
        except Exception as e:
            logger.error(f"Error occurred while fetching company data: {e}")

    # Run all company searches concurrently
    await asyncio.gather(*[fetch_company(input_data) for input_data in organizations])

    return companies


if __name__ == '__main__':

    async def main ():

        # Test out the search_people function
        response = await search_people(
            person_titles=["Founder"],
            q_keywords="Stealth",
            person_locations=["London, UK"],
            organization_locations=["London, UK"],
            per_page=10
        )

        pprint(response)

    asyncio.run(main())

    # resp = search_companies(
    #     page=1,
    #     per_page=10,
    #     # organization_num_employees_ranges=["1,100", "1,1000"],
    #     # organization_locations=["United States"],
    #     # organization_not_locations=["India"],
    #     q_organization_keyword_tags=["Venture Capitalist", "Business"],
    #     q_organization_name="Antler"
    # )
    #
    # pprint(resp)