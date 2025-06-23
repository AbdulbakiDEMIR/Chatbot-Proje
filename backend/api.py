from flask import Flask, Response, abort, request
from chatbot_class import Chatbot
from flask_cors import CORS  
import json

# Flask uygulaması oluşturuluyor
app = Flask(__name__)
CORS(app)  # CORS'u tüm domainler için etkinleştir (güvenli değilse domain kısıtlaması eklenebilir)

# Chatbot sınıfından bir örnek oluşturuluyor (uygulama başlarken yüklenir)
chatbot = Chatbot()

# Ana endpoint ('/') tanımlanıyor
@app.route('/', methods=['GET'])
def chat_bot():
    # URL üzerinden gelen "query" parametresi alınır (yoksa varsayılan metin)
    query = request.args.get("query", "Varsayılan metin")

    # Chatbot'a sorgu gönderilir ve cevap alınır
    response_data = chatbot.prompt(query)

    # JSON formatında cevap hazırlanır
    response_data = {
        "response": response_data 
    }

    # JSON yanıtı döndürülür, Türkçe karakter desteği için utf-8 belirtilir
    return Response(
        json.dumps(response_data, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )

# Uygulama doğrudan çalıştırıldığında başlatılır
if __name__ == '__main__':
    app.run(debug=True, port=1616)
