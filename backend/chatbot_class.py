import pandas as pd
import json
import os
from collections import defaultdict
from difflib import get_close_matches
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain


def data_preprocessing(data_path):
    with open(data_path, "r", encoding="utf-8") as f:
        books = json.load(f)

    # Dönüştürülmüş veri listesi
    rag_formatted = []

    for book in books:
        content = (
            f"{book['title']} - {book['genre']} türünde bir kitaptır, {book['author']} tarafından yazılmıştır. {book['summary']}"
            f"{book['price']} TL. Stok: {book['stock']} adet."
        )
        
        metadata = {
            "id": book["id"],
            "kitap_adi": book["title"].lower(),
            "yazar": book["author"].lower(),
            "tur": book["genre"].lower(),
            "fiyat": book["price"],
            "stok": book["stock"],
        }
        
        rag_formatted.append(Document(page_content=content, metadata=metadata))
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(rag_formatted)   

    return docs



class Chatbot:
    def __init__(self):
        self.docs = data_preprocessing("kitaplar_dataset.json")
        load_dotenv(override=True)
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY"))
        self.vectorstore = Chroma.from_documents(
            documents=self.docs,
            embedding=self.embeddings,
            persist_directory="./chroma_books_db_llm_9"
        )
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10}
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.3,
            max_tokens=500,
        )

        # System Prompt
        self.system_prompt = (
            "Sen bir kitapçı asistanısın. Kullanıcılara veritabanında bulunan kitaplara göre kitap tavsiyesi yapar, "
            "kitaplar hakkında bilgi verir, yazar ve tür bilgisi sunar, ayrıca stok ve fiyat bilgilerini paylaşırsın. "
            "Eğer kullanıcı bir kitap hakkında bilgi isterse özetini ver, eğer yazar sorarsa kitaplarını listele. "
            "Kullanıcı belirli bir türde kitap isterse o türdeki kitapları öner."
            "'Sepet İşlemi' olarak adlandırılan işlemlerde sadece kitap adını geri döndür."
            "Eğer sepet işlemleriyle alakalı bir durum varsa 'kitap_ekle', 'sepet_goster', 'sepet_temizle', 'sepet_toplam' ve 'kitap_cikar' intentlerinden uygun olanı döndür  "
            "Eğer sepet işlemi yapılıyorsa hiçbir açıklama olmadan intent-kitap_ismi şeklinde dönmeli "
            "Veritabanında olmayan bilgi sorulursa nazikçe bunu belirt.\n\n"
            "{context}"
        )

        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}")
        ])

        self.cart = []
    
    ## sepet işlemleri
    def add_book(self,book):
        book = book.lower()
        found = [
            doc for doc in self.retriever.invoke(book)
            if book in doc.metadata.get("kitap_adi", "").lower()
        ]
        if found:
            self.cart.append(found[0].metadata)
            return f"✅ '{found[0].metadata['kitap_adi']}' sepete eklendi."
        else:
            return f"❌ '{book}' adlı kitap bulunamadı."
        
    
    def delete_book(self,book):
        book = book.lower()
        silindi = False
        for item in self.cart:
            if book in item["kitap_adi"].lower():
                self.cart.remove(item)
                return f"❌ '{item['kitap_adi']}' sepetten çıkarıldı."
                silindi = True
                break
        if not silindi:
            return f"🔍 '{book}' adlı kitap sepette bulunamadı."
        
    def show_cart(self):
        if not self.cart:
            return "🛒 Sepet boş."
        else:
            mesajlar = ["📦 Sepetteki Kitaplar:"]
            for i, item in enumerate(self.cart, 1):
                mesajlar.append(f"{i}. {item['kitap_adi']} - {item['fiyat']} TL")
            return "\n".join(mesajlar)
    

    def delete_cart(self):
        self.cart.clear()
        return "🧹 Sepet temizlendi."
        return True

    def total_cost(self):
        toplam = sum(item["fiyat"] for item in self.cart)
        return f"💰 Toplam Tutar: {toplam} TL"
        return True


    def prompt(self,query):
        # print (query)
        question_answer_chain = create_stuff_documents_chain(self.llm, self.prompt_template)
        rag_chain = create_retrieval_chain(self.retriever, question_answer_chain)
        response = rag_chain.invoke({"input": query})
        answer = response["answer"]
        intents = ["kitap_ekle","sepet_goster","sepet_temizle","sepet_toplam","kitap_cikar"]
        if any(k in answer.lower() for k in intents):
            parts = answer.split("-")
            intent= ""
            book= "" 
            if len(parts) == 2:
                intent, book = parts
            else:
                intent= answer
            
            if intent == "kitap_ekle":
                return self.add_book(book)
            elif intent == "kitap_cikar":
                return self.delete_book(book)
            elif intent == "sepet_goster":
                return self.show_cart()
            elif intent == "sepet_temizle":
                return self.delete_cart()
            elif intent == "sepet_toplam":
                return self.total_cost()

        else:
            return answer

        
