import re
import uuid
from typing import List, Dict


Q_PATTERN = re.compile(r"^##\s*Q:\s*(.+)", re.IGNORECASE)
A_PATTERN = re.compile(r"^A:\s*(.+)", re.IGNORECASE)


class QnAChunker:
    """
    Converts Markdown FAQ into structured Q&A chunks.
    Designed for service-layer usage (no CLI logic).
    """

    def parse(self, md_text: str) -> List[Dict]:
        lines = md_text.splitlines()

        chunks = []
        current_q = None
        current_a = []

        def flush():
            nonlocal current_q, current_a

            if not current_q or not current_a:
                return

            answer = " ".join(current_a).strip()

            chunks.append({
                "id": str(uuid.uuid4()),
                "question": current_q.strip(),
                "answer": answer,
                "text": f"Q: {current_q}\nA: {answer}"
            })

            current_q = None
            current_a = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            q_match = Q_PATTERN.match(line)

            if q_match:
                flush()
                current_q = q_match.group(1).strip()

                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()

                    if Q_PATTERN.match(next_line):
                        break

                    a_match = A_PATTERN.match(next_line)
                    if a_match:
                        current_a.append(a_match.group(1).strip())
                    elif next_line:
                        current_a.append(next_line)

                    i += 1
                continue

            i += 1

        flush()
        return chunks