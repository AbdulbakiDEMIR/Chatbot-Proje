# Gerekli kütüphanelerin içe aktarımı
import os
import json
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI


# Kitap verilerini işleyip RAG formatına dönüştüren fonksiyon
def data_preprocessing(data_path):
    with open(data_path, "r", encoding="utf-8") as f:
        books = json.load(f)

    rag_formatted = []

    for book in books:
        # Kitap bilgilerini tek bir string olarak birleştir
        content = (
            f"{book['title']} - {book['genre']} türünde bir kitaptır, {book['author']} tarafından yazılmıştır. {book['summary']}"
            f"{book['price']} TL. Stok: {book['stock']} adet."
        )
        
        # Metadata bilgileri
        metadata = {
            "id": book["id"],
            "kitap_adi": book["title"].lower(),
            "yazar": book["author"].lower(),
            "tur": book["genre"].lower(),
            "fiyat": book["price"],
            "stok": book["stock"],
        }
        
        # LangChain Document objesi olarak ekle
        rag_formatted.append(Document(page_content=content, metadata=metadata))
    
    # Metni parçalara ayır (chunk) - daha verimli vektörleme için
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(rag_formatted)   

    return docs


# Chatbot sınıfı
class Chatbot:
    def __init__(self):
        # .env dosyasındaki API anahtarlarını yükle
        load_dotenv(override=True)

        # Google Generative AI embedding modeli
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", api_key=os.getenv("GOOGLE_API_KEY"))
        
        # Vektör veritabanını yükle
        self.upload_vectorstore("./chroma_books_db")

        # Benzerlik tabanlı retriever ayarla
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 10}
        )

        # Gemini LLM modeli (düşük gecikmeli)
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.3,
            max_tokens=500,
        )

        # Sistem promptu: LLM'e görevini anlatır
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

        # Prompt şablonu (sistem + kullanıcı mesajı)
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{input}")
        ])

        # Sepet başlangıçta boş
        self.cart = []
    
    # Vektör veritabanını yükleme veya oluşturma
    def upload_vectorstore(self, persist_dir):
        if os.path.exists(persist_dir) and os.path.exists(os.path.join(persist_dir, "index")):
            # Var olan veritabanını yükle
            self.vectorstore = Chroma(
                persist_directory=persist_dir,
                embedding=self.embeddings
            )
        else:
            # Yeni veritabanı oluştur
            self.docs = data_preprocessing("kitaplar_dataset.json")
            self.vectorstore = Chroma.from_documents(
                documents=self.docs,
                embedding=self.embeddings,
                persist_directory=persist_dir
            )
    
    
    # Kitap sepete ekle
    def add_book(self, book):
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
        
    # Kitabı sepetten çıkar
    def delete_book(self, book):
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
        
    # Sepeti göster
    def show_cart(self):
        if not self.cart:
            return "🛒 Sepet boş."
        else:
            mesajlar = ["📦 Sepetteki Kitaplar:"]
            for i, item in enumerate(self.cart, 1):
                mesajlar.append(f"{i}. {item['kitap_adi']} - {item['fiyat']} TL")
            return "\n".join(mesajlar)
    
    # Sepeti tamamen temizle
    def delete_cart(self):
        self.cart.clear()
        return "🧹 Sepet temizlendi."
        return True  # (not: bu satıra asla ulaşılamaz)

    # Sepetteki kitapların toplam fiyatını döndür
    def total_cost(self):
        toplam = sum(item["fiyat"] for item in self.cart)
        return f"💰 Toplam Tutar: {toplam} TL"
        return True  # (not: bu satıra da ulaşılamaz)


    # Kullanıcıdan gelen prompta cevap üret
    def prompt(self, query):
        # LLM zincirini oluştur
        question_answer_chain = create_stuff_documents_chain(self.llm, self.prompt_template)
        rag_chain = create_retrieval_chain(self.retriever, question_answer_chain)

        # Zinciri çalıştır ve yanıt al
        response = rag_chain.invoke({"input": query})
        answer = response["answer"]

        # Sepetle ilgili bir işlem olup olmadığını kontrol et
        intents = ["kitap_ekle", "sepet_goster", "sepet_temizle", "sepet_toplam", "kitap_cikar"]
        if any(k in answer.lower() for k in intents):
            parts = answer.split("-")
            intent = ""
            book = "" 
            if len(parts) == 2:
                intent, book = parts
            else:
                intent = answer
            
            # İlgili sepet fonksiyonunu çalıştır
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
            # Normal yanıt döndür
            return answer
