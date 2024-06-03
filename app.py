import os

import streamlit as st
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.memory import ChatMessageHistory
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceEndpoint, HuggingFaceTextGenInference
from langchain_community.vectorstores import Chroma
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableBranch, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_text_splitters import RecursiveCharacterTextSplitter
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

import utils
from env import INFERENCE_SERVER_URL, OTLP_ENDPOINT, SVC_NAME, TOKENIZER_NAME

# os.environ["HUGGINGFACEHUB_API_TOKEN"] = HUGGINGFACEHUB_API_TOKEN

provider = TracerProvider(resource=Resource.create({SERVICE_NAME: SVC_NAME}))
otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)


st.set_page_config(page_title="ChatPDF", page_icon="📄")
st.header("Chat with your documents")
st.write(
    "Has access to custom documents and can respond to user queries by referring to the content within those documents"
)


class CustomDataChatbot:
    @tracer.start_as_current_span("Initialize")
    def __init__(self):
        self.inference_server_url = INFERENCE_SERVER_URL
        self.llm = HuggingFaceEndpoint(
            endpoint_url=self.inference_server_url,
            task="text-generation",
            max_new_tokens=512,
            top_k=1,
            top_p=0.95,
            typical_p=0.95,
            temperature=0.01,
            repetition_penalty=1.03,
        )
        self.embedding = HuggingFaceEmbeddings(
            model_name=TOKENIZER_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.demo_ephemeral_chat_history = ChatMessageHistory()

    def save_file(self, file):
        folder = "tmp"
        if not os.path.exists(folder):
            os.makedirs(folder)

        file_path = f"./{folder}/{file.name}"
        with open(file_path, "wb") as f:
            f.write(file.getvalue())
        return file_path

    @tracer.start_as_current_span("get retriever")
    def get_retriever(self, uploaded_files):
        # Load documents
        docs = []
        for file in uploaded_files:
            file_path = self.save_file(file)
            loader = PyPDFLoader(file_path)
            docs.extend(loader.load())

        # Split documents
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500, chunk_overlap=200
        )
        splits = text_splitter.split_documents(docs)
        vectorstore = Chroma.from_documents(documents=splits, embedding=self.embedding)

        # Define retriever
        self.retriever = vectorstore.as_retriever(
            search_type="mmr", search_kwargs={"k": 2, "fetch_k": 4}
        )

    @tracer.start_as_current_span("Get query transform chain")
    def get_query_transform_chain(self):
        query_transform_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                (
                    "user",
                    "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation. Only respond with the query, nothing else.",
                ),
            ]
        )

        self.query_transforming_retriever_chain = RunnableBranch(
            (
                lambda x: len(x.get("messages", [])) == 1,
                # If only one message, then we just pass that message's content to retriever
                (lambda x: x["messages"][-1].content) | self.retriever,
            ),
            # If messages, then we pass inputs to LLM chain to transform the query, then pass to retriever
            query_transform_prompt | self.llm | StrOutputParser() | self.retriever,
        ).with_config(run_name="chat_retriever_chain")

    def query_chain(self, chain_input):
        stored_messages = self.demo_ephemeral_chat_history.messages
        if len(stored_messages) == 0:
            return self.query_transforming_retriever_chain.invoke(
                {"messages": [HumanMessage(chain_input["input"])]},
            )
        return self.query_transforming_retriever_chain.invoke(
            {"messages": stored_messages + [HumanMessage(chain_input["input"])]},
        )

    @tracer.start_as_current_span("Set up")
    def setup_qa_chain(self, uploaded_files):
        self.get_retriever(uploaded_files)
        self.get_query_transform_chain()

        SYSTEM_TEMPLATE = """
        Answer the user's questions based on the below context.
        If the context doesn't contain any relevant information to the question, don't make something up and just say "I don't know":

        <context>
        {context}
        </context>
        """

        question_answering_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    SYSTEM_TEMPLATE,
                ),
                MessagesPlaceholder(variable_name="messages"),
                ("user", "{input}"),
            ]
        )

        document_chain = create_stuff_documents_chain(
            self.llm, question_answering_prompt
        )
        chain_with_message_history = RunnableWithMessageHistory(
            document_chain,
            lambda session_id: self.demo_ephemeral_chat_history,
            input_messages_key="input",
            history_messages_key="messages",
        )

        qa_chain = (
            RunnablePassthrough.assign(context=self.query_chain)
            | chain_with_message_history
        )

        return qa_chain

    @tracer.start_as_current_span("Main")
    @utils.enable_chat_history
    def main(self):
        with tracer.start_as_current_span("server_request"):
            # User Inputs
            uploaded_files = st.sidebar.file_uploader(
                label="Upload PDF files", type=["pdf"], accept_multiple_files=True
            )
            if not uploaded_files:
                st.error("Please upload PDF documents to continue!")
                st.stop()

            user_query = st.chat_input(placeholder="Ask me anything!")

            if uploaded_files and user_query:
                qa_chain = self.setup_qa_chain(uploaded_files)

                st.chat_message("user").write(user_query)
                st.session_state.messages.append(
                    {"role": "user", "content": user_query}
                )

                with tracer.start_as_current_span("Response time"):
                    response = qa_chain.invoke(
                        {"input": user_query},
                        {"configurable": {"session_id": "unused"}},
                    )
                st.chat_message("assistant").write(response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )


if __name__ == "__main__":
    obj = CustomDataChatbot()
    obj.main()
