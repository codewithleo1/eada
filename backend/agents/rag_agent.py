"""
rag_agent.py — RAG agent for the EADA multi-agent graph.

Handles document questions using the Phase 3 RAG pipeline.
Retrieves relevant chunks from Qdrant then generates an answer.

Reads:  state["user_message"], state["doc_id"], state["plan"]
Writes: state["rag_context"], state["final_answer"], state["next_agent"]
"""

from __future__ import annotations

from backend.agents.state import AgentState, AGENT_CRITIC
from backend.rag.rag_pipeline import retrieve_context, build_rag_context, RAGPipelineError
from backend.llm.gateway import llm
from backend.observability.logging import get_logger

log = get_logger(__name__)


async def rag_agent_node(state: AgentState) -> AgentState:
    """
    LangGraph node — answers document questions using RAG.

    Reads:  state["user_message"], state["doc_id"], state["plan"]
    Writes: state["rag_context"], state["final_answer"], state["next_agent"]
    """
    user_message = state.get("user_message", "")
    doc_id = state.get("doc_id")
    plan = state.get("plan", [])

    log.info("rag_agent.start", message=user_message[:80], doc_id=doc_id)

    if not doc_id:
        log.warning("rag_agent.no_doc")
        return {
            "final_answer": "No document is attached. Please ingest a document first.",
            "next_agent": AGENT_CRITIC,
        }

    # Use plan steps as search query if available
    query = "\n".join(plan) if plan else user_message

    # Retrieve relevant chunks from Qdrant
    try:
        chunks = retrieve_context(query, top_k=5, doc_id=doc_id)
        rag_context = build_rag_context(chunks)
    except RAGPipelineError as e:
        log.error("rag_agent.retrieval_failed", error=str(e))
        return {
            "rag_context": "",
            "final_answer": f"Document retrieval failed: {e}",
            "next_agent": AGENT_CRITIC,
            "error": str(e),
        }

    log.info("rag_agent.retrieved", num_chunks=len(chunks))

    # Generate answer using retrieved context
    system_prompt = (
        "You are an expert analyst with access to relevant document sections. "
        "Use ONLY the following document context to answer the question. "
        "If the answer is not in the context, say so clearly.\n\n"
        f"DOCUMENT CONTEXT:\n{rag_context}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        final_answer = await llm.complete(messages=messages)
    except Exception as e:
        log.error("rag_agent.llm_failed", error=str(e))
        return {
            "rag_context": rag_context,
            "final_answer": f"Answer generation failed: {e}",
            "next_agent": AGENT_CRITIC,
            "error": str(e),
        }

    log.info("rag_agent.done", answer_length=len(final_answer))

    return {
        "rag_context": rag_context,
        "final_answer": final_answer,
        "next_agent": AGENT_CRITIC,
    }
