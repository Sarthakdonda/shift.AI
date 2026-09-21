"use client";

import { T } from "@/components/locale";
import type { DiscoveryQuestion, Message } from "@/lib/types";
import styles from "./question-card.module.css";

export function messageQuestions(message: Message): DiscoveryQuestion[] {
  if (message.role !== "assistant" || message.message_type !== "question")
    return [];
  return message.questions?.length
    ? message.questions
    : [
        {
          question: message.content,
          topic: `legacy.${message.id}`,
          reason: "",
        },
      ];
}

export function QuestionContent({
  questions,
  numbers,
  notice,
  headingId,
}: {
  questions: DiscoveryQuestion[];
  numbers: number[];
  notice?: string;
  headingId?: string;
}) {
  return (
    <div className={styles.content}>
      {notice && <p className={styles.notice}>{notice}</p>}
      {questions.map((question, index) => (
        <div className={styles.question} key={`${question.topic}-${index}`}>
          <div className={styles.eyebrow}>
            <span>
              <T text="Question" /> {numbers[index]}
            </span>
            <span className={styles.dot} aria-hidden="true" />
            <span>{question.label || <T text="Your project" />}</span>
          </div>
          <h3 id={index === 0 ? headingId : undefined}>{question.question}</h3>
          {question.reason && (
            <p className={styles.reason}>{question.reason}</p>
          )}
          {question.hint && <p className={styles.hint}>{question.hint}</p>}
        </div>
      ))}
    </div>
  );
}

export { styles as questionStyles };
