from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ========== TASK 1: READ PDF ==========
print("\n📄 TASK 1: Loading PDF...")
reader = PdfReader("rahul_resume-final.pdf")

full_text = ""
for page in reader.pages:
    full_text += page.extract_text()

print(f"✅ Loaded: {len(reader.pages)} pages, {len(full_text)} characters")
print("="*60)


# ========== TASK 2: CHUNKING ==========
print("\n📦 TASK 2: Chunking text...")

def chunk_text(text, chunk_size=1500, overlap=300):
    """Universal chunking for any document"""
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        if chunk:
            chunks.append(chunk)
        
        start += chunk_size - overlap
    
    return chunks

chunks = chunk_text(full_text, chunk_size=1500, overlap=300)
print(f"✅ Created {len(chunks)} chunks")
print("="*60)


# ========== TASK 3: EMBEDDINGS ==========
print("\n🧠 TASK 3: Creating embeddings...")
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(chunks)
print(f"✅ Created {len(embeddings)} embeddings")
print("="*60)


# ========== TASK 4: STORE IN DATABASE ==========
print("\n💾 TASK 4: Storing in ChromaDB...")
client = chromadb.Client()
collection = client.create_collection("my_documents")

for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
    collection.add(
        ids=[f"chunk_{i}"],
        embeddings=[embedding.tolist()],
        documents=[chunk]
    )

print(f"✅ Stored {len(chunks)} chunks")
print("="*60)


# ========== TASK 5: GEMINI INTEGRATION ==========
print("\n🤖 TASK 5: Setting up Gemini AI...")

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Gemini model
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

def ask_question(question, top_k=3):
    """
    Ask a question and get an answer from Gemini using retrieved context.
    
    Args:
        question: The user's question
        top_k: Number of relevant chunks to retrieve
    
    Returns:
        answer: The answer from Gemini
        sources: The chunks used as context
    """
    print(f"\n🔍 Processing question: {question}")
    
    # Step 1: Convert question to embedding
    print("  → Converting question to embedding...")
    question_embedding = model.encode([question])[0]
    
    # Step 2: Search for relevant chunks
    print("  → Searching for relevant chunks...")
    results = collection.query(
        query_embeddings=[question_embedding.tolist()],
        n_results=top_k
    )
    
    # Step 3: Get the retrieved chunks
    relevant_chunks = results['documents'][0]
    print(f"  → Found {len(relevant_chunks)} relevant chunks")
    
    # Step 4: Build context from chunks
    context = "\n\n".join(relevant_chunks)
    
    # Step 5: Create prompt for Gemini
    prompt = f"""You are a helpful assistant that answers questions based on provided context.

Context:
{context}

Question: {question}

Instructions:
- Answer based ONLY on the information in the context above
- If the answer is not in the context, say "I don't have enough information to answer that question."
- Be concise and accurate
- Use bullet points if listing multiple items

Answer:"""
    
    # Step 6: Call Gemini
    print("  → Getting answer from Gemini...")
    response = gemini_model.generate_content(prompt)
    
    # Step 7: Extract answer
    answer = response.text
    
    return answer, relevant_chunks


print("✅ Gemini AI ready!")
print("="*60)


# ========== TESTING THE COMPLETE RAG SYSTEM ==========
print("\n" + "="*60)
print("🎉 COMPLETE RAG SYSTEM TEST")
print("="*60)

# Test questions
test_questions = [
    "What is this document about? Summarize briefly.",
    "What programming languages and technologies does this person know?",
    "What is the work experience?",
    "What projects has this person built?",
    "What is the educational background?"
]

print("\nTesting with multiple questions...\n")

for i, question in enumerate(test_questions, 1):
    print(f"\n{'='*60}")
    print(f"TEST {i}/{len(test_questions)}")
    print('='*60)
    print(f"❓ QUESTION: {question}")
    print('-'*60)
    
    try:
        # Get answer
        answer, sources = ask_question(question, top_k=2)
        
        # Display answer
        print(f"\n🤖 GEMINI ANSWER:")
        print(answer)
        
        # Show sources (optional)
        print(f"\n📚 Sources used ({len(sources)} chunks):")
        for j, source in enumerate(sources, 1):
            print(f"\n  📄 Source {j} (first 150 chars):")
            print(f"     {source[:150]}...")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")

print("\n" + "="*60)
print("🎉 ALL TASKS COMPLETE!")
print("="*60)
print("\n✨ Your RAG System is fully working!")
print("   ✅ Task 1: PDF Loading")
print("   ✅ Task 2: Text Chunking")
print("   ✅ Task 3: Embeddings")
print("   ✅ Task 4: Vector Storage")
print("   ✅ Task 5: Gemini Q&A")
print("\n🚀 Next: Make it interactive or add a UI!")