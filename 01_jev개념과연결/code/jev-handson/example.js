import { readFile } from "node:fs/promises";
import { OpenRouter } from "@openrouter/sdk";

const apiKey = (await readFile(new URL("./env.txt", import.meta.url), "utf8")).trim();

if (!apiKey) {
  throw new Error("env.txt에 OpenRouter API 키가 없습니다.");
}

const openrouter = new OpenRouter({ apiKey });

// The model answers narrow, typed questions about the state. Your code owns the workflow.
const decision = await openrouter.alpha.decisions.create({
  decisionsRequest: {
    model: "~typesafe/jev-latest",
    state: "Help! My payouts have been failing for 3 days.",
    questions: {
      is_urgent: {
        type: "noul",
        instructions: "Does this message convey urgency?",
        criteria: {
          true: "Explicitly time-sensitive",
          false: "No urgency expressed"
        }
      },
      department: {
        type: "choice",
        instructions: "Which team should handle this?",
        criteria: {
          billing: "Payments, invoicing, refunds",
          technical: "Bugs, outages, integrations",
          sales: "Pricing, upgrades, new accounts"
        }
      },
      frustration: {
        type: "score",
        instructions: "How frustrated is the customer?",
        criteria: ["Calm", "Frustrated", "Very angry"]
      }
    }
  }
});

const { is_urgent, department, frustration } = decision.answers;

if (
  is_urgent.type === "noul" &&
  department.type === "choice" &&
  frustration.type === "score"
) {
  console.log({
    urgencyProbability: is_urgent.noul,
    department: department.choice,
    departmentProbabilities: department.probabilities,
    frustrationScore: frustration.score
  });

  if (is_urgent.noul > 0.8 && department.choice === "billing") {
    console.log("Escalation condition matched: urgent billing issue.");
  }
}
