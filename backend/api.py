from flask import Flask, Response, abort, request
from chatbot_class import Chatbot
from flask_cors import CORS
import json

app = Flask(__name__)
CORS(app)  
chatbot = Chatbot()

@app.route('/', methods=['GET'])
def only_once():
    query = request.args.get("query", "Varsayılan metin")
    response_data = chatbot.prompt(query)
    response_data = {
        "respone": response_data
    }
    return Response(
        json.dumps(response_data, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )

if __name__ == '__main__':
    app.run(debug=True)
