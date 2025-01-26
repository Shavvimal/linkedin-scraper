import os
import requests
from api.utils.brave import Brave
from urllib.parse import quote
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.schema import Document
from langchain_openai import AzureChatOpenAI
from typing import List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph, START
from dotenv import load_dotenv
from logging import getLogger
from pprint import pprint
from api.utils.logger import setup_logger
from api.models.find import SearchCompaniesInput, SearchCompaniesInputs

_ = load_dotenv()

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        question: question
        entities: LLM list of entities
        web_search: whether to add search
        documents: list of documents
    """

    question: str
    extracted_entities: List[SearchCompaniesInput]
    web_search: str
    documents: List[Document]

class SearchAgent:
    def __init__(self, entity_type: str):
        self.workflow = None
        self.entity_type = entity_type
        self.llm = self.setup_llm()
        # Chains
        self.entity_extraction_chain = None
        self.retrieval_grader = None
        self.question_rewriter = None
        self.logger = getLogger(f"API.{__name__}")

        # Set up the workflow
        self.setup_entity_extraction_chain()
        self.setup_retrieval_grader()
        self.setup_question_rewriter()
        self.setup_workflow()

    def setup_llm(self):
        return AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_ID"),
            api_version=os.getenv("AZURE_OPENAI_CHAT_API_VERSION"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            # organization="...",
            # model="gpt-35-turbo",
            # model_version="0125",
            # other params...
        )

    def setup_entity_extraction_chain(self):
        parser = PydanticOutputParser(pydantic_object=SearchCompaniesInputs)

        prompt = PromptTemplate(
            template="""
            You are a researcher doing research on {entity_type}. Use the following pieces of retrieved context from websites you found during your search to extract all the relevant {entity_type} from the resource. If you cant find any relevant {entity_type}, just return none. Wrong answers are worse than no answers.
            
            Question: {question} 
            Context: {context} 
            
            {format_instructions}
            
            Only fill in the values you are certain of. If you are unsure or there is no relevant information, leave the field blank with None.
            """,
            input_variables=["entity_type", "question", "context"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        self.entity_extraction_chain = prompt | self.llm | parser

        # prompt = """
        # You are a researcher doing research on {entity_type}. Use the following pieces of retrieved context from websites you found during your search to extract all the relevant {entity_type} from the resource. If you cant find any relevant {entity_type}, just return none. Wrong answers are worse than no answers.
        #
        # Question: {question}
        # Context: {context}
        #
        # Your response should be a list of comma separated values. For example, the format we want is:
        #
        # eg: `foo, bar, baz` or `foo,bar,baz`
        #
        # Where the names of the {entity_type} are seperated by a comma.
        #
        # Extracted and relevant {entity_type} i.e. Answer:
        #
        #
        # """
        # prompt_template = PromptTemplate.from_template(prompt)
        # output_parser = CommaSeparatedListOutputParser()
        # self.entity_extraction_chain = prompt_template | self.llm | output_parser

    def setup_retrieval_grader(self):
        class GradeDocuments(BaseModel):
            """Binary score for relevance check on retrieved documents."""
            binary_score: str = Field(
                description="Documents are relevant to the question, 'yes' or 'no'"
            )

        structured_llm_grader = self.llm.with_structured_output(GradeDocuments)

        system = f"""You are a grader assessing relevance of a retrieved content to a users question. The user is trying to gather a list of {self.entity_type} based on certain criteria. If the document contains many {self.entity_type} related to the question, grade it as relevant. Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question."""

        grade_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("human", "Retrieved document: \n\n {document} \n\n User question: {question}"),
            ]
        )

        self.retrieval_grader = grade_prompt | structured_llm_grader

    def setup_question_rewriter(self):
        system = f"""You a question re-writer that converts an input question to a better version that is optimized for web search. Look at the input, and and try to reason about the underlying semantic intent / meaning. Then reformat the question into a web query that is most likely to return results that would contain a list of {self.entity_type}"""

        re_write_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                (
                    "human",
                    "Here is the initial question: \n\n {question} \n Formulate an improved question.",
                ),
            ]
        )

        self.question_rewriter = re_write_prompt | self.llm | StrOutputParser()

    def brave_search(self, query: str, num_results: int = 3):
        brave = Brave()
        search_results = brave.search(q=query, count=num_results)

        urls = [f"https://r.jina.ai/{quote(str(doc.get('url')), safe=':/')}"
                for doc in search_results.web_results]

        fetched_contents = []
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                fetched_contents.append({'url': url, 'status_code': response.status_code, 'content': response.text})
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching content from {url}: {e}")
        return fetched_contents

    def tavily_search(self, query: str, num_results: int = 3):
        tavily_search_tool = TavilySearchResults(tavily_api_key=os.getenv("TAVILY_API_KEY"), k=num_results)
        search_results = tavily_search_tool.invoke({'query': query})
        urls = [f"https://r.jina.ai/{result['url']}" for result in search_results]

        fetched_contents = []
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                fetched_contents.append({'url': url, 'status_code': response.status_code, 'content': response.text})
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching content from {url}: {e}")

        return fetched_contents

    def web_search(self, state):
        """
        Retrieve documents using a web search. Start with Brave, fallback to Tavily.

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, documents, that contains web search documents
        """

        self.logger.info("---RETRIEVE FROM WEB SEARCH---")
        question = state["question"]
        documents = []

        try:
            brave_search_res = self.brave_search(question, num_results=1)
            if not brave_search_res:
                raise ValueError("Brave search returned no results.")

            for result in brave_search_res:
                documents.append(Document(page_content=result["content"]))
            self.logger.info(f"---SUCCESS: RETRIEVED {len(brave_search_res)} RESULTS FROM BRAVE---")

        except Exception as e:
            self.logger.info(f"---FAILED: BRAVE SEARCH ERROR: {e}, FALLING BACK TO TAVILY---")

            try:
                tavily_search_res = self.tavily_search(question)
                if not tavily_search_res:
                    raise ValueError("Tavily search returned no results.")

                for result in tavily_search_res:
                    documents.append(Document(page_content=result["content"]))
                self.logger.info(f"---SUCCESS: RETRIEVED {len(tavily_search_res)} RESULTS FROM TAVILY---")

            except Exception as e:
                self.logger.info(f"---FAILED: TAVILY SEARCH ERROR: {e}---")
                documents.append(Document(page_content="No results found from web search."))

        return {"documents": documents, "question": question}

    def grade_documents(self, state):
        """
        Determines whether the retrieved documents are relevant to the question.

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): Updates documents key with only filtered relevant documents
        """

        self.logger.info("---CHECK DOCUMENT RELEVANCE TO QUESTION---")
        question = state["question"]
        documents = state["documents"]

        filtered_docs = []
        web_search = "No"
        for d in documents:
            score = self.retrieval_grader.invoke({"question": question, "document": d.page_content})
            grade = score.binary_score
            if grade == "yes":
                self.logger.info("---GRADE: DOCUMENT RELEVANT---")
                filtered_docs.append(d)
            else:
                self.logger.info("---GRADE: DOCUMENT NOT RELEVANT---")
                continue

        # If all documents are not relevant, we will re-generate a new query
        if not filtered_docs:
            web_search = "Yes"

        return {"documents": filtered_docs, "question": question, "web_search": web_search}

    def extract_entities(self, state):
        """
        Generate Entities from the documents.

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation, that contains LLM generation
        """

        # Run Extraction chain for each of the docs and add the companies to a set

        question = state["question"]
        documents = state["documents"]
        extracted_entities = []

        # Run entity extraction for each document
        for doc in documents:
            doc_txt = doc.page_content
            if not doc_txt:
                continue

            extraction_result = self.entity_extraction_chain.invoke({
                "entity_type": self.entity_type,
                "question": question,
                "context": doc_txt
            })

            if extraction_result:
                extracted_entities.extend(extraction_result)


        return {"documents": documents, "extracted_entities": list(extracted_entities), "question": question}

    def transform_query(self, state):
        """
        Transform the query to produce a better question.

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): Updates question key with a re-phrased question
        """

        self.logger.info("---TRANSFORM QUERY---")
        question = state["question"]
        better_question = self.question_rewriter.invoke({"question": question})
        return {"documents": state["documents"], "question": better_question}

    def decide_to_generate(self, state):
        """
        Edge that determines whether to generate an answer, or re-generate a question.

        Args:
            state (dict): The current graph state

        Returns:
            str: Binary decision for next node to call
        """

        self.logger.info("---ASSESS GRADED DOCUMENTS---")

        web_search = state["web_search"]

        if web_search == "Yes":
            # All documents have been filtered check_relevance
            # We will re-generate a new query
            self.logger.info(
                "---DECISION: ALL DOCUMENTS ARE NOT RELEVANT TO QUESTION, TRANSFORM QUERY---"
            )
            return "transform_query"
        else:
            # We have relevant documents, so generate answer
            self.logger.info("---DECISION: EXTRACT ENTITIES---")
            return "extract_entities"

    def setup_workflow(self):
        workflow = StateGraph(GraphState)
        # Define the nodes
        workflow.add_node("web_search_node", self.web_search)
        workflow.add_node("grade_documents", self.grade_documents)
        workflow.add_node("extract_entities", self.extract_entities)
        workflow.add_node("transform_query", self.transform_query)
        workflow.add_node("web_search_retry", self.web_search)
        # Build graph
        workflow.add_edge(START, "web_search_node")
        workflow.add_edge("web_search_node", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            self.decide_to_generate,
            {
                "transform_query": "transform_query",
                "extract_entities": "extract_entities",
            },
        )
        workflow.add_edge("transform_query", "web_search_retry")
        workflow.add_edge("web_search_retry", "extract_entities")
        workflow.add_edge("extract_entities", END)
        # Compile
        self.workflow = workflow.compile()

    def invoke(self, question: str):
        if not self.workflow:
            raise ValueError("Workflow not set up.")

        # Stream the workflow
        # inputs = {"question": question}
        # for output in self.workflow.stream(inputs):
        #     for key, value in output.items():
        #         # Node
        #         pprint(f"Node '{key}':")
        #         # Optional: print full state at each node
        #         pprint(value, indent=2, width=80, depth=None)
        #     pprint("\n---\n")

        res = self.workflow.invoke({"question": question})
        return res["extracted_entities"]


if __name__ == '__main__':
    setup_logger()
    search_agent = SearchAgent("companies")
    result = search_agent.invoke("Give me the top manufacturing companies in Virginia USA")
    print(result)
