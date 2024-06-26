import base64
import io
import os
import re

import google.generativeai as genai
import pinecone
import tensorflow as tf

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from flask_cors import CORS
from langchain.document_loaders import PyPDFLoader

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Pinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from reportlab.pdfgen import canvas
from weasyprint import HTML

os.environ["PINECONE_API_KEY"] = "0e51bceb-f4be-436e-8ce6-7b3f37b379c9"

app = Flask(__name__)
CORS(app, resources={r"/predict": {"origins": "http://localhost:3000"}})
load_dotenv()

model_predict = tf.keras.models.load_model("model_DenseNet121_Full_Sample.h5")
loader = PyPDFLoader("disease_compendium.pdf")
data = loader.load()
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100,
    length_function=len,
    add_start_index=True,
)
texts = text_splitter.split_documents(data)

page_contents = [doc.page_content for doc in texts]
page_contents_pinecone = [str(content) for content in page_contents]

preprocessed_page_contents = [page_content.lower() for page_content in page_contents]


genai.configure(api_key="AIzaSyBODPD0qgF01nIW_XT4qcOUdSn3eQV1JAs")
model = genai.GenerativeModel("gemini-pro")
model_embed = "models/embedding-001"
pinconde_index_list = ['us-west-1a']
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001",
    google_api_key="AIzaSyBODPD0qgF01nIW_XT4qcOUdSn3eQV1JAs",
)

index_name = "lung_disease"
# Create and configure index if doesn't already exist
if index_name in pinconde_index_list:
    pinecone.create_index(name=index_name, metric="cosine", dimension=1536)
    docsearch = Pinecone.from_documents(texts, embeddings, index_name=index_name)


def process_user_input(user_input, text_user):
    if len(user_input) == 0:
        query = """
"""
    query = (
        """The array provided symbolizes if the user has potentially a chest selected medically condition. The array shows 1 if the user has the corresponding disease and 0 otherwise.
    The order of diseases are No Finding, Enlarged Cardiomediastinum,Cardiomegaly,Lung Opacity,Lung Lesion,Edema,Consolidation,Pneumonia,Atelectasis,Pneumothorax,Pleural Effusion,Pleural Other,Fracture, Support Devices. Based on the diseases from the array and the symptoms the user is showing, provide all the diseases and list down their symptoms, what are possible lifestyle changes and what can be the possible treatments for this.
    The order of diseases are No Finding, Enlarged Cardiomediastinum,Cardiomegaly,Lung Opacity,Lung Lesion,Edema,Consolidation,Pneumonia,Atelectasis,Pneumothorax,Pleural Effusion,Pleural Other,Fracture, Support Devices. Based on the diseases from the array and the symptoms the user is showing, provide all the diseases and list down their symptoms, what are possible lifestyle changes and what can be the possible treatments for this.
    The following are some of the symptoms the user is facing, explain the user more about these symptoms and how to cure them: """
        + text_user
        + """The array indicating the presence of diseases is as follows: """
        + user_input
    )
    result = model.generate_content(query)
    print(result)
    return result


def generate_pdf_content(result):
    parts = result._result.candidates[0].content.parts
    text_content = "\n\n".join(part.text for part in parts)

    text_content = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text_content)

    text_content = text_content.replace("\n", "<br>")

    buffer = io.BytesIO()
    html_content = f"<html><body>{text_content}</body></html>"
    HTML(string=html_content).write_pdf(buffer)

    buffer.seek(0)
    pdf_content = buffer.read()
    base64_pdf_content = base64.b64encode(pdf_content).decode("utf-8")
    return base64_pdf_content


def generate_pdf(result, filename):
    buffer = io.BytesIO()
    html_content = f"<html><body>{result}</body></html>"
    HTML(string=html_content).write_pdf(buffer)

    buffer.seek(0)
    with open(filename, "wb") as f:
        f.write(buffer.read())


def preprocess_image(image):
    image = tf.image.grayscale_to_rgb(image)
    image = tf.image.resize(image, [224, 224])
    image_array = tf.image.convert_image_dtype(image, dtype=tf.uint8)
    image_array = tf.image.convert_image_dtype(image, dtype=tf.uint8)
    return image_array


def predict_label(image_data):
    image = tf.image.decode_jpeg(image_data)
    preprocessed_image = preprocess_image(image)

    prediction = model_predict.predict(tf.expand_dims(preprocessed_image, axis=0))[0]

    prediction_list = prediction.tolist()

    return prediction_list


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    file = request.files["file"]
    text_user = request.form["text"]
    print("User input text:", text_user)
    image_data = file.read()

    p = predict_label(image_data)

    print("Predictions:", p)
    result = process_user_input(str(p), str(text_user))
    print(result)

    pdf_content = generate_pdf_content(result)

    return jsonify({"prediction": p, "pdfcontent": pdf_content})


@app.route("/output", methods=["GET"])
def output():
    pdf_filename = "output.pdf"
    return send_file(pdf_filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
