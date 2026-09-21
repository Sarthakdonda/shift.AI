"use client";

import { Info, Lightbulb } from "lucide-react";
import type { DiscoveryQuestion, Message } from "@/lib/types";

/** Older transcripts stored the question as plain assistant content. */
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

export type ActiveQuestion = {
  questions: DiscoveryQuestion[];
  numbers: number[];
  notice?: string;
};

/**
 * The discovery question design: a numbered label, the topic it belongs to, the
 * question itself, why it is being asked, and an optional hint. The same block
 * renders inside the transcript and inside the answer surface, so a question
 * never looks like two different things.
 */
export function QuestionContent({
  questions,
  numbers,
  notice,
  headingId,
}: ActiveQuestion & { headingId?: string }) {
  return (
    <div className="qcard-body">
      {notice && (
        <p className="qnotice">
          <Info size={14} aria-hidden="true" />
          <span>{notice}</span>
        </p>
      )}
      {questions.map((question, index) => (
        <div className="question" key={`${question.topic}-${index}`}>
          <div className="qeyebrow">
            <span className="qnumber">Question {numbers[index] || index + 1}</span>
            <span className="qdot" aria-hidden="true" />
            <span className="qtopic">{question.label || "Your project"}</span>
          </div>
          <h3 id={index === 0 ? headingId : undefined} className="selectable">
            {question.question}
          </h3>
          {question.reason && (
            <p className="qreason">
              <Info size={13} aria-hidden="true" />
              <span>{question.reason}</span>
            </p>
          )}
          {question.hint && (
            <p className="qhint">
              <Lightbulb size={13} aria-hidden="true" />
              <span>{question.hint}</span>
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export function QuestionCard(props: ActiveQuestion) {
  return (
    <div className="qcard">
      <QuestionContent {...props} />
    </div>
  );
}
