from openai import OpenAI
import streamlit as st
import os
from PIL import Image
import base64
import io
from PyPDF2 import PdfReader
from docx import Document
import tempfile
from typing import List, Dict, Union

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set page configuration
st.set_page_config(page_title="Multimodal Chat App")

# Display logo
st.image('Logo_Landscape_Colored.png', width=300)
st.title("Prompting Guide")

# Initialize session state
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4-vision-preview"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None

def extract_text_from_pdf(file_bytes) -> str:
    """
    Extract text from PDF using PyPDF2
    Returns text content
    """
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    text_content = []
    
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text_content.append(f"Page {page_num + 1}:\n{page.extract_text()}")
    
    return "\n".join(text_content)

def extract_text_from_docx(file_bytes) -> str:
    """Extract text from DOCX file"""
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def process_uploaded_file(uploaded_file) -> Union[Dict, List[Dict], None]:
    """Process the uploaded file and return appropriate content for the message"""
    if uploaded_file is None:
        return None
    
    file_type = uploaded_file.type
    
    if file_type.startswith('image'):
        # Handle images
        image = Image.open(uploaded_file)
        
        # Convert to base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{image_str}",
                "detail": "high"
            }
        }
    
    elif file_type == 'application/pdf':
        # Extract text from PDF
        text_content = extract_text_from_pdf(uploaded_file.getvalue())
        
        # Store extracted content in session state for reference
        st.session_state.document_content = text_content
        
        return {
            "type": "text",
            "text": text_content
        }
    
    elif file_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        # Handle DOCX files
        text_content = extract_text_from_docx(uploaded_file.getvalue())
        
        # Store extracted content in session state for reference
        st.session_state.document_content = text_content
        
        return {
            "type": "text",
            "text": text_content
        }
    
    elif file_type == 'text/plain':
        # Handle text files
        text_content = uploaded_file.getvalue().decode()
        st.session_state.document_content = text_content
        return {
            "type": "text",
            "text": text_content
        }
    
    return None

# File uploader with expanded file types
uploaded_file = st.file_uploader(
    "Upload a file", 
    type=['png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt']
)

# Document content viewer (collapsible)
if st.session_state.document_content:
    with st.expander("View Document Content"):
        st.text(st.session_state.document_content)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], str):
            st.markdown(message["content"])
        elif isinstance(message["content"], list):
            # Handle multimodal content
            for content in message["content"]:
                if isinstance(content, dict):
                    if content.get("type") == "image_url":
                        # Display images
                        image_url = content["image_url"]["url"]
                        if image_url.startswith('data:image'):
                            image_data = base64.b64decode(image_url.split(',')[1])
                            st.image(image_data)
                    elif content.get("type") == "text":
                        st.markdown(content["text"])
                else:
                    st.markdown(str(content))

# Chat input
if prompt := st.chat_input("What is up?"):
    # Process any uploaded file
    file_content = process_uploaded_file(uploaded_file)
    
    # Prepare the message content
    if isinstance(file_content, list):
        message_content = [{"type": "text", "text": prompt}] + file_content
    elif file_content:
        message_content = [{"type": "text", "text": prompt}, file_content]
    else:
        message_content = [{"type": "text", "text": prompt}]
    
    # Add user message to session state
    st.session_state.messages.append({"role": "user", "content": message_content})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
        if file_content:
            if isinstance(file_content, list):
                for content in file_content:
                    if content.get("type") == "image_url":
                        image_url = content["image_url"]["url"]
                        if image_url.startswith('data:image'):
                            image_data = base64.b64decode(image_url.split(',')[1])
                            st.image(image_data)
                    elif content.get("type") == "text":
                        with st.expander("Uploaded Document Content"):
                            st.markdown(content["text"])
            elif file_content.get("type") == "image_url":
                image_url = file_content["image_url"]["url"]
                if image_url.startswith('data:image'):
                    image_data = base64.b64decode(image_url.split(',')[1])
                    st.image(image_data)
            elif file_content.get("type") == "text":
                with st.expander("Uploaded Document Content"):
                    st.markdown(file_content["text"])
    
    # Generate assistant response
    with st.chat_message("assistant"):
        stream = client.chat.completions.create(
            model=st.session_state["openai_model"],
            messages=[
                {"role": m["role"], 
                 "content": m["content"] if isinstance(m["content"], str) else [
                     c if isinstance(c, str) else c
                     for c in m["content"]
                 ]}
                for m in st.session_state.messages
            ],
            stream=True,
        )
        response = st.write_stream(stream)
    
    # Add assistant response to session state
    st.session_state.messages.append({"role": "assistant", "content": response})

# Add a clear button
if st.button("Clear Chat History"):
    st.session_state.messages = []
    st.session_state.document_content = None
    st.experimental_rerun()
