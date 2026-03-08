from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb
import google.generativeai as genai
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

class UniversalRAG:
    """RAG system that works with ANY PDF"""
    
    def __init__(self):
        print("🚀 Initializing Universal RAG System...")
        
        # Load models
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.llm = genai.GenerativeModel('gemini-2.5-flash')
        
        # Initialize vector DB
        self.chroma_client = chromadb.Client()
        self.collection = None
        
        print("✅ System initialized!")
    
    def load_pdf(self, pdf_path: str) -> dict:
        """
        Load and analyze any PDF file
        Returns metadata about the document
        """
        print(f"\n📄 Loading PDF: {pdf_path}")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Read PDF
        reader = PdfReader(pdf_path)
        
        # Extract all text
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text()
        
        # Get metadata
        metadata = {
            'filename': Path(pdf_path).name,
            'num_pages': len(reader.pages),
            'num_characters': len(full_text),
            'num_words': len(full_text.split())
        }
        
        print(f"✅ Loaded: {metadata['num_pages']} pages, "
              f"{metadata['num_characters']} characters")
        
        # Check if PDF has enough text
        if len(full_text) < 100:
            print("⚠️  WARNING: Very little text extracted!")
            print("   This might be a scanned PDF (image-based)")
            print("   Consider using OCR or a different PDF")
        
        return full_text, metadata
    
    def chunk_text(self, text: str, chunk_size: int = 1500, 
                   overlap: int = 300) -> list:
        """
        Universal chunking strategy
        Works for any document type
        """
        print(f"\n📦 Chunking text...")
        print(f"   Chunk size: {chunk_size} chars")
        print(f"   Overlap: {overlap} chars")
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()
            
            if chunk:
                chunks.append(chunk)
            
            start += chunk_size - overlap
        
        print(f"✅ Created {len(chunks)} chunks")
        
        # Provide feedback on chunking
        if len(chunks) > 100:
            print(f"⚠️  Note: {len(chunks)} chunks is quite large")
            print(f"   Consider increasing chunk_size for better performance")
        
        return chunks
    
    def create_embeddings(self, chunks: list) -> list:
        """Create embeddings for all chunks"""
        print(f"\n🧠 Creating embeddings for {len(chunks)} chunks...")
        
        embeddings = self.embedding_model.encode(
            chunks, 
            show_progress_bar=True
        )
        
        print(f"✅ Created {len(embeddings)} embeddings")
        return embeddings
    
    def store_in_database(self, chunks: list, embeddings: list, 
                         doc_name: str):
        """Store chunks and embeddings in vector database"""
        print(f"\n💾 Storing in vector database...")
        
        # Create new collection for this document
        collection_name = f"doc_{doc_name.replace('.pdf', '').replace(' ', '_')}"
        
        # Delete if exists
        try:
            self.chroma_client.delete_collection(collection_name)
        except:
            pass
        
        self.collection = self.chroma_client.create_collection(collection_name)
        
        # Store all chunks
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            self.collection.add(
                ids=[f"chunk_{i}"],
                embeddings=[embedding.tolist()],
                documents=[chunk]
            )
        
        print(f"✅ Stored {len(chunks)} chunks in collection: {collection_name}")
    
    def ask_question(self, question: str, top_k: int = 3) -> dict:
        """
        Ask a question about the loaded document
        Returns answer and sources
        """
        if self.collection is None:
            raise ValueError("No document loaded! Call ingest_pdf() first.")
        
        print(f"\n❓ Question: {question}")
        print(f"🔍 Searching for relevant information...")
        
        # Embed question
        question_embedding = self.embedding_model.encode([question])[0]
        
        # Search vector DB
        results = self.collection.query(
            query_embeddings=[question_embedding.tolist()],
            n_results=top_k
        )
        
        relevant_chunks = results['documents'][0]
        print(f"✅ Found {len(relevant_chunks)} relevant chunks")
        
        # Build context
        context = "\n\n".join(relevant_chunks)
        
        # Create prompt
        prompt = f"""You are a helpful assistant that answers questions based on provided context.

Context from document:
{context}

Question: {question}

Instructions:
- Answer based ONLY on the information in the context above
- If the answer is not in the context, say "I don't have enough information to answer that."
- Be concise and accurate
- If listing items, use bullet points

Answer:"""
        
        # Get answer from LLM
        print("🤖 Generating answer...")
        response = self.llm.generate_content(prompt)
        answer = response.text
        
        return {
            'answer': answer,
            'sources': relevant_chunks,
            'num_sources': len(relevant_chunks)
        }
    
    def ingest_pdf(self, pdf_path: str):
        """
        Complete pipeline: Load, chunk, embed, store
        """
        print("\n" + "="*60)
        print("📚 INGESTING DOCUMENT")
        print("="*60)
        
        # Load
        text, metadata = self.load_pdf(pdf_path)
        
        # Chunk
        chunks = self.chunk_text(text)
        
        # Embed
        embeddings = self.create_embeddings(chunks)
        
        # Store
        self.store_in_database(chunks, embeddings, metadata['filename'])
        
        print("\n" + "="*60)
        print("✅ DOCUMENT READY FOR QUERIES")
        print("="*60)
        
        return metadata
    
    def interactive_qa(self):
        """Interactive Q&A session"""
        print("\n💬 Interactive Q&A Mode")
        print("Type 'quit' to exit\n")
        
        while True:
            question = input("❓ Your question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not question:
                continue
            
            try:
                result = self.ask_question(question)
                print(f"\n🤖 Answer:\n{result['answer']}\n")
                print(f"📚 Based on {result['num_sources']} source(s)\n")
            except Exception as e:
                print(f"❌ Error: {e}\n")


# ==================== TESTING FUNCTION ====================

def test_multiple_pdfs():
    """Test the system with multiple PDFs"""
    
    # Find all PDFs in current directory
    pdf_files = list(Path('.').glob('*.pdf'))
    
    if not pdf_files:
        print("❌ No PDF files found in current directory")
        print("Please add some PDF files and try again")
        return
    
    print(f"\n📚 Found {len(pdf_files)} PDF file(s):")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"  {i}. {pdf.name}")
    
    # Test each PDF
    for pdf_path in pdf_files:
        print("\n" + "="*70)
        print(f"TESTING: {pdf_path.name}")
        print("="*70)
        
        try:
            # Initialize system
            rag = UniversalRAG()
            
            # Ingest document
            metadata = rag.ingest_pdf(str(pdf_path))
            
            # Test with generic questions
            test_questions = [
                "What is this document about? Provide a brief summary.",
                "What are the main topics or themes discussed?",
                "List the key points or takeaways from this document."
            ]
            
            print("\n" + "="*60)
            print("TESTING QUESTIONS")
            print("="*60)
            
            for question in test_questions:
                print(f"\n{'─'*60}")
                result = rag.ask_question(question, top_k=2)
                print(f"🤖 Answer:\n{result['answer']}")
                print(f"\n📄 Source preview: {result['sources'][0][:150]}...")
            
        except Exception as e:
            print(f"\n❌ Error testing {pdf_path.name}: {e}")
            continue


# ==================== SINGLE PDF MODE ====================

def interactive_mode(pdf_path: str):
    """Load one PDF and start interactive Q&A"""
    
    rag = UniversalRAG()
    
    # Ingest the document
    rag.ingest_pdf(pdf_path)
    
    # Start Q&A
    rag.interactive_qa()


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║         UNIVERSAL RAG SYSTEM - TEST MODE                  ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    if len(sys.argv) > 1:
        # Single PDF mode
        pdf_path = sys.argv[1]
        print(f"📄 Loading: {pdf_path}\n")
        interactive_mode(pdf_path)
    else:
        # Test all PDFs mode
        print("🧪 Testing all PDFs in current directory\n")
        test_multiple_pdfs()