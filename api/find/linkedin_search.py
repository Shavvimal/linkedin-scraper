from typing import List
from api.models.find import SearchTemplate
from api.utils.linkedin_api import Linkedin


def search_people_by_template(linkedin_scraper: Linkedin, search_template: SearchTemplate) -> List[str]:
    # Construct a natural language search query from the search_template
    query_parts = []

    if search_template.person_title:
        query_parts.append(f"{search_template.person_title}")

    if search_template.job_title_keywords:
        query_parts.append(" ".join(search_template.job_title_keywords))

    if search_template.about_job:
        query_parts.append(f"{search_template.about_job}")

    if search_template.job_description_keywords:
        query_parts.append(" ".join(search_template.job_description_keywords))

    if search_template.location:
        query_parts.append(f"{search_template.location}")

    if search_template.previous_locations:
        query_parts.append(" ".join(search_template.previous_locations))

    if search_template.companies:
        query_parts.append(" ".join(search_template.companies))

    if search_template.education:
        query_parts.append(" ".join(search_template.education))

    if search_template.time_current_role:
        time_role = search_template.time_current_role
        duration_str = f"{time_role.duration} {time_role.unit}(s)"
        query_parts.append(f"current role {time_role.qualifier} {duration_str}")

    # Join all parts to form the final search query
    query = ". ".join(query_parts)
    print(query)

    # Call the search_people function with the constructed query
    results = linkedin_scraper.search(
        params={"keywords": query},
        limit=10
    )

    linkedin_urls = []

    for i in range(len(results)):
        url = results[i].get("actorNavigationUrl")
        if url:
            # remove query parameters from the URL
            url = url.split("?")[0]
            # We want people, so we only want those with /in/ in the url
            if "/in/" in url:
                linkedin_urls.append(url)

    return linkedin_urls


def scrape_person_data(linkedin_scraper:Linkedin, urn: str):

    # GET a profile
    result = linkedin_scraper.get_profile(urn)

    person = {
        "first_name": result.get("firstName"),
        "last_name": result.get("lastName"),
        "headline": result.get("headline"),
        "location": result.get("locationName"),
        "industry": result.get("industryName"),
        "profile_url": f"https://www.linkedin.com/in/{result.get('public_id')}",
        "summary": result.get("summary"),
        "skills": [skill.get("name") for skill in result.get("skills", [])],
        "experience": [
            {
                "title": exp.get("title"),
                "company_name": exp.get("companyName"),
                "location": exp.get("locationName"),
                "start_date": exp.get("timePeriod", {}).get("startDate"),
                "end_date": exp.get("timePeriod", {}).get("endDate"),
                "description": exp.get("description")
            }
            for exp in result.get("experience", [])
        ],
        "education": [
            {
                "school_name": edu.get("schoolName"),
                "degree": edu.get("degreeName"),
                "field_of_study": edu.get("fieldOfStudy")
            }
            for edu in result.get("education", [])
        ],
        "certifications": [
            {
                "name": cert.get("name"),
                "authority": cert.get("authority"),
                "start_date": cert.get("timePeriod", {}).get("startDate")
            }
            for cert in result.get("certifications", [])
        ],
        "projects": result.get("projects", []),
        "publications": result.get("publications", []),
        "volunteer": result.get("volunteer", []),
        "languages": result.get("languages", []),
        "profile_picture": result.get("displayPictureUrl")
    }

    return person





if __name__ == '__main__':
    import os
    from dotenv import load_dotenv
    from pprint import pprint

    load_dotenv()


    # Login to LinkedIn
    email = os.environ.get("LINKEDIN_EMAIL")
    password = os.environ.get("LINKEDIN_PASSWORD")

    # Authenticate using any Linkedin user account credentialslin
    scraper = Linkedin(
        email,
        password
    )

    # Create a dummy search template for hiring managers in startups
    search_data = {
        "person_title": "Hiring Manager",
        "job_title_keywords": ["startup", "tech"],
        "about_job": "Hiring manager in startup",
        "job_description_keywords": ["recruitment", "talent acquisition", "tech"],
        "location": "UK",
        "companies": [],
        "education": ["University of California"]
    }

    # Cast the search data to the SearchTemplate model
    search_template = SearchTemplate(**search_data)

    # Perform the search and print the results
    search_results = search_people_by_template(scraper, search_template)
    pprint(search_results)


    urn = ['https://www.linkedin.com/in/ACoAAAC8f08BPdRluH_cGxnh8UZHfw5lwJ-M4Mc',
     'https://www.linkedin.com/in/ACoAAEhiZMUBdN57UTSfGRIRRZlcg1AmBA005xA',
     'https://www.linkedin.com/in/ACoAAAOwDeUB6IszsFVUg9DOSfjwpJaCYxULIDI',
     'https://www.linkedin.com/in/ACoAAAcCUr8BI6i7mhit18M1ZMi0-wx_3G0SgiA']

    person = scrape_person_data(scraper, urn[0].split('/')[-1])
    pprint(person)