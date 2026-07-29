import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";
import { prisma } from "./prisma";

const NO_ANSWER_REPLY =
  "Sorry, I don't have that information yet. Kindly reach out to the church admin for help.";

const FAQ_PATH = path.join(process.cwd(), "..", "backend", "app", "data", "faq.md");
const EMBED_MODEL = process.env.OPENAI_EMBED_MODEL?.trim() || "text-embedding-3-small";
const CHAT_MODEL = process.env.OPENAI_CHAT_MODEL?.trim() || "gpt-4o-mini";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY?.trim() || "";

type FaqChunk = {
  id: string;
  source: string;
  question: string;
  answer: string;
  text: string;
  score?: number | null;
};

type ChatResult = {
  answer: string;
  answered: boolean;
  topScore: number | null;
};

const answerCache = new Map<string, { expiresAt: number; value: string }>();
const CACHE_TTL_MS = 15 * 60 * 1000;
const CACHE_MAX_ENTRIES = 300;

function hasPrismaErrorCode(error: unknown, ...codes: string[]) {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    codes.includes(String((error as { code?: unknown }).code))
  );
}

function normalizeToken(token: string) {
  const value = token.toLowerCase().trim();
  if (value.length > 4 && value.endsWith("ies")) return `${value.slice(0, -3)}y`;
  if (value.length > 3 && value.endsWith("s")) return value.slice(0, -1);
  return value;
}

function tokens(text: string) {
  return new Set(
    (text.toLowerCase().match(/[a-zA-Z0-9']+/g) ?? [])
      .filter((token) => token.length > 2)
      .map(normalizeToken)
  );
}

function sourceHintBonus(question: string, chunk: FaqChunk) {
  const q = question.toLowerCase();
  const source = chunk.source.toLowerCase();
  let bonus = 0;
  if (q.includes("connect") && source.includes("/connect")) bonus += 4;
  if (q.includes("service") && source.includes("/home")) bonus += 2;
  if (q.includes("pastor") && source.includes("/about")) bonus += 2;
  if (q.includes("sermon") && source.includes("/sermons")) bonus += 2;
  return bonus;
}

function normalizeQuestion(question: string) {
  return question.toLowerCase().trim().replace(/\s+/g, " ").replace(/[^a-z0-9\s]/g, "");
}

function isLowInformationAnswer(answer: string) {
  const normalized = answer.toLowerCase().trim();
  return [
    "i don't have enough information",
    "i do not have enough information",
    "i don't know",
    "not enough information",
  ].some((marker) => normalized.includes(marker));
}

function isCountOrListingQuery(question: string) {
  const q = question.toLowerCase();
  return ["how many", "count", "total", "list", "all of"].some((marker) => q.includes(marker));
}

function expandQueryTokens(queryTokens: Set<string>, vocab: Set<string>) {
  const expanded = new Set(queryTokens);
  for (const token of queryTokens) {
    if (token.length < 4) continue;
    let bestMatch = "";
    let bestScore = 0;
    for (const candidate of vocab) {
      let matches = 0;
      const maxLen = Math.max(token.length, candidate.length);
      for (let i = 0; i < Math.min(token.length, candidate.length); i += 1) {
        if (token[i] === candidate[i]) matches += 1;
      }
      const score = matches / maxLen;
      if (score > bestScore) {
        bestScore = score;
        bestMatch = candidate;
      }
    }
    if (bestMatch && bestScore >= 0.8) expanded.add(bestMatch);
  }
  return expanded;
}

function mergeContexts(question: string, vectorContext: FaqChunk[], lexicalContext: FaqChunk[], topK: number) {
  const merged: FaqChunk[] = [];
  const seen = new Set<string>();

  for (const chunk of [...lexicalContext, ...vectorContext]) {
    const key = `${chunk.question}\u0000${chunk.answer}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(chunk);
  }

  const questionTokens = tokens(question);
  merged.sort((left, right) => {
    const leftOverlap =
      [...questionTokens].filter((token) => {
        const combined = new Set([...tokens(left.question), ...tokens(left.answer)]);
        return combined.has(token);
      }).length + sourceHintBonus(question, left);
    const rightOverlap =
      [...questionTokens].filter((token) => {
        const combined = new Set([...tokens(right.question), ...tokens(right.answer)]);
        return combined.has(token);
      }).length + sourceHintBonus(question, right);
    return rightOverlap - leftOverlap;
  });

  return merged.slice(0, topK);
}

function readSeedFaqChunks() {
  if (!fs.existsSync(FAQ_PATH)) return [];

  const markdown = fs.readFileSync(FAQ_PATH, "utf8");
  const lines = markdown.split(/\r?\n/);
  const chunks: FaqChunk[] = [];
  let currentSource = "unknown";
  let currentQuestion: string | null = null;
  let currentAnswer: string[] = [];

  const flush = () => {
    if (!currentQuestion || currentAnswer.length === 0) return;
    const answer = currentAnswer.join(" ").trim();
    chunks.push({
      id: `${currentSource}:${chunks.length}`,
      source: currentSource,
      question: currentQuestion,
      answer,
      text: `Q: ${currentQuestion}\nA: ${answer}`,
    });
    currentQuestion = null;
    currentAnswer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith("# Source:")) {
      flush();
      currentSource = line.replace("# Source:", "").trim();
      continue;
    }
    if (line.startsWith("## Q:")) {
      flush();
      currentQuestion = line.replace("## Q:", "").trim();
      continue;
    }
    if (line.startsWith("A:")) {
      currentAnswer.push(line.replace("A:", "").trim());
      continue;
    }
    if (currentQuestion && line) {
      currentAnswer.push(line);
    }
  }

  flush();
  return chunks;
}

async function readKbChunks() {
  let entries: Array<{ id: string; source: string | null; question: string; answer: string }> = [];
  try {
    entries = await prisma.kb_entries.findMany({
      orderBy: { created_at: "desc" },
      take: 500,
    });
  } catch (error) {
    if (!hasPrismaErrorCode(error, "P2021", "P2022")) {
      throw error;
    }
    return [];
  }

  return entries.map((entry: { id: string; source: string | null; question: string; answer: string }) => ({
    id: `admin:${entry.id}`,
    source: entry.source || "admin",
    question: entry.question,
    answer: entry.answer,
    text: `Q: ${entry.question}\nA: ${entry.answer}`,
  }));
}

async function createEmbedding(input: string) {
  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: EMBED_MODEL,
      input,
    }),
  });

  if (!response.ok) {
    throw new Error(`Embedding request failed with ${response.status}`);
  }

  const data = (await response.json()) as {
    data?: Array<{ embedding?: number[] }>;
  };
  const embedding = data.data?.[0]?.embedding;
  if (!embedding) {
    throw new Error("Embedding response did not include a vector.");
  }
  return embedding;
}

async function vectorSearch(embedding: number[], topK: number) {
  const vectorLiteral = `[${embedding.map((value) => Number(value).toString()).join(",")}]`;
  let rows: Array<{
    id: string;
    question: string | null;
    answer: string | null;
    text: string | null;
    metadata: unknown;
    score: number | null;
  }> = [];

  try {
    rows = (await prisma.$queryRawUnsafe(
      `
        SELECT id, question, answer, text, metadata,
               1 - (embedding <=> $1::vector) AS score
        FROM faq_embeddings
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> $1::vector
        LIMIT $2
      `,
      vectorLiteral,
      topK
    )) as Array<{
      id: string;
      question: string | null;
      answer: string | null;
      text: string | null;
      metadata: unknown;
      score: number | null;
    }>;
  } catch (error) {
    if (!hasPrismaErrorCode(error, "P2021", "P2022")) {
      throw error;
    }
    return [];
  }

  return rows
    .filter((row: { question: string | null; answer: string | null }) => row.question && row.answer)
    .map((row: {
      id: string;
      question: string | null;
      answer: string | null;
      text: string | null;
      metadata: unknown;
      score: number | null;
    }) => ({
      id: row.id,
      source:
        row.metadata && typeof row.metadata === "object" && !Array.isArray(row.metadata)
          ? String((row.metadata as Record<string, unknown>).source ?? "unknown")
          : "unknown",
      question: row.question as string,
      answer: row.answer as string,
      text: row.text || `Q: ${row.question}\nA: ${row.answer}`,
      score: row.score,
    }));
}

async function generateAnswer(question: string, context: FaqChunk[]) {
  const contextText = context.map((chunk) => `Q: ${chunk.question}\nA: ${chunk.answer}`).join("\n\n");

  const prompt = `You are a warm, friendly assistant for The Votage church, talking with website visitors. Always sound welcoming and kind.

The CONTEXT below is the church's full knowledge base — a set of question/answer pairs. Read across ALL of it and connect related entries.

Decide how to respond to the QUESTION:

1. CHURCH-SPECIFIC facts about The Votage (service times, location, leaders, events, dates, giving/amounts, programs, ministries, groups, or church policies):
   - If the CONTEXT covers it, answer using ONLY the context. Read across all entries and combine related ones. Match partial, shortened, or informal names to the fuller item — e.g. "connect" -> "Connect Group"; "refresh" -> the church's Refresh offerings such as the Refresh Miracle Service and the Refresh Tour; asking about "church" time -> the service times; "growth track" -> the membership / Growth Track class.
   - Only if the church's knowledge base genuinely does not cover the topic at all, do NOT guess — reply with EXACTLY: I don't have enough information.

2. GENERAL or common-sense questions that are NOT specific to The Votage (e.g. what to wear to church in general, general etiquette, broadly Christian questions):
   - Give a warm, brief, faith-appropriate general answer. Do not present it as official Votage policy unless it is in the CONTEXT.

3. PERSONAL or PASTORAL questions (counselling, emotional support, prayer requests, personal spiritual advice, crisis, grief, relationships, finances, health, or anything that needs a caring human):
   - Do NOT try to counsel or advise. Reply with EXACTLY: I don't have enough information.

CONTEXT:
${contextText}

QUESTION:
${question}

ANSWER:`;

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: CHAT_MODEL,
      temperature: 0.3,
      max_tokens: 400,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat completion failed with ${response.status}`);
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string | null } }>;
  };
  const answer = data.choices?.[0]?.message?.content?.trim();
  if (!answer) {
    throw new Error("Chat completion response was empty.");
  }
  return answer;
}

async function logChat(sessionId: string, question: string, answer: string, answered: boolean, topScore: number | null) {
  try {
    await prisma.chat_logs.create({
      data: {
        id: randomUUID(),
        session_id: sessionId,
        question,
        answer,
        answered,
        top_score: topScore,
      },
      select: {
        id: true,
      },
    });
  } catch (error) {
    console.error("chat log insert failed", error);
  }
}

function cacheGet(key: string) {
  const item = answerCache.get(key);
  if (!item) return null;
  if (item.expiresAt < Date.now()) {
    answerCache.delete(key);
    return null;
  }
  answerCache.delete(key);
  answerCache.set(key, item);
  return item.value;
}

function cacheSet(key: string, value: string) {
  if (isLowInformationAnswer(value)) return;
  answerCache.set(key, { expiresAt: Date.now() + CACHE_TTL_MS, value });
  while (answerCache.size > CACHE_MAX_ENTRIES) {
    const oldestKey = answerCache.keys().next().value;
    if (!oldestKey) break;
    answerCache.delete(oldestKey);
  }
}

function lexicalSearch(question: string, chunks: FaqChunk[], vocab: Set<string>, topK: number) {
  if (chunks.length === 0) return [];
  const normalizedQuestion = question.toLowerCase();
  let queryTokens = expandQueryTokens(tokens(question), vocab);
  if (normalizedQuestion.startsWith("what about ")) {
    queryTokens = new Set([
      ...queryTokens,
      ...expandQueryTokens(tokens(normalizedQuestion.replace("what about ", "")), vocab),
    ]);
  }

  const scored = chunks
    .map((chunk) => {
      const chunkTokens = new Set([...tokens(chunk.question), ...tokens(chunk.answer)]);
      const overlap = [...queryTokens].filter((token) => chunkTokens.has(token)).length;
      const score = overlap + sourceHintBonus(question, chunk);
      return { chunk, score };
    })
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);

  return scored.slice(0, topK).map((item) => item.chunk);
}

async function askWithMeta(question: string): Promise<ChatResult> {
  if (!OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is not set for the frontend chat service.");
  }

  const cacheKey = normalizeQuestion(question);
  const cached = cacheGet(cacheKey);
  if (cached) {
    return { answer: cached, answered: true, topScore: null };
  }

  const allChunks = [...readSeedFaqChunks(), ...(await readKbChunks())];
  const vocab = new Set<string>();
  for (const chunk of allChunks) {
    for (const token of tokens(chunk.question)) vocab.add(token);
    for (const token of tokens(chunk.answer)) vocab.add(token);
    for (const token of tokens(chunk.source.replace(/\//g, " "))) vocab.add(token);
  }

  const useWideContext = isCountOrListingQuery(question);
  const lexicalContext = lexicalSearch(question, allChunks, vocab, useWideContext ? 12 : 6);

  try {
    const queryEmbedding = await createEmbedding(question);
    const vectorContext = await vectorSearch(queryEmbedding, useWideContext ? 10 : 6);
    const topScore = Math.max(...vectorContext.map((chunk: FaqChunk) => chunk.score ?? 0), 0);
    const relevant = mergeContexts(question, vectorContext, lexicalContext, useWideContext ? 12 : 7);
    const seen = new Set(relevant.map((chunk: FaqChunk) => `${chunk.question}\u0000${chunk.answer}`));
    const context = [
      ...relevant,
      ...allChunks.filter((chunk: FaqChunk) => !seen.has(`${chunk.question}\u0000${chunk.answer}`)),
    ];
    const answer = await generateAnswer(question, context);

    if (isLowInformationAnswer(answer)) {
      return { answer: NO_ANSWER_REPLY, answered: false, topScore };
    }

    cacheSet(cacheKey, answer);
    return { answer, answered: true, topScore };
  } catch (error) {
    console.error("FAQ primary path failed, using fallback", error);
    if (lexicalContext.length > 0) {
      try {
        const answer = await generateAnswer(question, lexicalContext);
        if (!isLowInformationAnswer(answer)) {
          cacheSet(cacheKey, answer);
          return { answer, answered: true, topScore: null };
        }
      } catch (fallbackError) {
        console.error("FAQ fallback path failed", fallbackError);
      }
    }
    return { answer: NO_ANSWER_REPLY, answered: false, topScore: null };
  }
}

export async function handleFaq(sessionId: string, message: string) {
  const result = await askWithMeta(message);
  await logChat(sessionId, message, result.answer, result.answered, result.topScore);
  return result.answer;
}
