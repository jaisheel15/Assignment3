import "dotenv/config";
import fs from "fs";

import { PDFLoader } from "@langchain/community/document_loaders/fs/pdf";

import { RecursiveCharacterTextSplitter } from "@langchain/textsplitters";

import { HuggingFaceInferenceEmbeddings } from "@langchain/community/embeddings/hf";

import { QdrantVectorStore } from "@langchain/qdrant";

import { ChatGroq } from "@langchain/groq";

import { QdrantClient } from "@qdrant/js-client-rest";


const filePath = "./marathas.pdf";

const QDRANT_API_KEY = process.env.QDRANT_API_KEY;
const QDRANT_URL = process.env.QDRANT_URL || "https://1cc5c39b-8eac-4b8d-9ed0-9bf92fcd7cfc.us-east-1-0.aws.cloud.qdrant.io";
const COLLECTION_NAME = "marathas_documents";

if (!QDRANT_API_KEY) {
    console.error("Missing Qdrant API key. Set QDRANT_API_KEY in your environment.");
    process.exit(1);
}

// Qdrant client
const qdrantClient = new QdrantClient({
    url: QDRANT_URL,
    apiKey: QDRANT_API_KEY,
});


// ======================================
// EMBEDDING MODEL
// ======================================

const HF_API_KEY = process.env.HUGGINGFACE_API_KEY ;
if (!HF_API_KEY) {
    console.error("Missing Hugging Face API key. Set HUGGINGFACE_API_KEY or HF_API_KEY in your environment.");
    console.error("For example: export HUGGINGFACE_API_KEY=your_token_here");
    process.exit(1);
}

const embeddings = new HuggingFaceInferenceEmbeddings({
    model: "sentence-transformers/all-MiniLM-L6-v2",
    apiKey: HF_API_KEY,
});


// ======================================
// INDEXING PIPELINE
// ======================================

async function indexing() {

    // 1. Load PDF
    const loader = new PDFLoader(filePath);

    const docs = await loader.load();

    console.log(`Loaded ${docs.length} pages`);


    // 2. Chunking
    const splitter = new RecursiveCharacterTextSplitter({
        chunkSize: 1000,
        chunkOverlap: 200,
    });

    const splitDocs = await splitter.splitDocuments(docs);

    console.log(`Created ${splitDocs.length} chunks`);


    // 3. Create Qdrant Vector Store
    const vectorStore = await QdrantVectorStore.fromDocuments(
        splitDocs,
        embeddings,
        {
            client: qdrantClient,
            collectionName: COLLECTION_NAME,
        }
    );

    console.log("Qdrant indexing completed");
}


// ======================================
// RETRIEVAL + GENERATION
// ======================================

async function retrieval() {

    const userQuery =
        "who where the marathas? what are their history and significance?";


    // 1. Load Qdrant vector store
    const vectorStore = await QdrantVectorStore.fromExistingCollection(
        embeddings,
        {
            client: qdrantClient,
            collectionName: COLLECTION_NAME,
        }
    );


    // 2. Retrieve similar chunks
    const results = await vectorStore.similaritySearch(
        userQuery,
        3
    );


    // 3. Build Context
    const context = results
        .map((doc, index) => {
            return `
Chunk ${index + 1}:
${doc.pageContent}
`;
        })
        .join("\n----------------------\n");


    // ======================================
    // GROQ MODEL
    // ======================================

    const llm = new ChatGroq({
        apiKey: process.env.GROQ_API_KEY,
        model: "llama-3.3-70b-versatile",
        temperature: 0,
    });


    const systemPrompt = `
You are a RAG AI assistant.

Answer ONLY from the provided context.

If the answer is not available in the context, say:
"I could not find the answer in the document."

Context:
${context}
`;


    // 4. Generate Response
    const response = await llm.invoke([
        {
            role: "system",
            content: systemPrompt,
        },
        {
            role: "user",
            content: userQuery,
        },
    ]);


    console.log("\n===== ANSWER =====\n");

    console.log(response.content);
}


// ======================================
// RUN
// ======================================

// Run (guarded)
async function runAll() {
    const pdfExists = fs.existsSync(filePath);

    if (!pdfExists) {
        console.error(`Missing resources: ${filePath} not found.`);
        console.error("Place the PDF at the path or run indexing with the PDF available.");
        return;
    }

    try {
        // Always try to index first (will create or update collection)
        await indexing();
        // Then retrieve after indexing
        await retrieval();
    } catch (error) {
        console.error("Error during RAG pipeline:", error.message);
        process.exit(1);
    }
}

runAll();