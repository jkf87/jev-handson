import { readFile } from "node:fs/promises";
import { OpenRouter } from "@openrouter/sdk";

const apiKey = (await readFile(new URL("./env.txt", import.meta.url), "utf8")).trim();

if (!apiKey) {
  throw new Error("env.txt에 OpenRouter API 키가 없습니다.");
}

const openrouter = new OpenRouter({ apiKey });
const model = "~typesafe/jev-latest";

// 1. noul: 질문에 대한 yes 확률을 0~1 값으로 반환합니다.
const noulDecision = await openrouter.alpha.decisions.create({
  decisionsRequest: {
    model,
    state: "Help! My payouts have been failing for 3 days.",
    questions: {
      is_urgent: {
        type: "noul",
        instructions: "Does this message convey urgency?",
        criteria: {
          true: "Explicitly time-sensitive or requires prompt action",
          false: "No urgency expressed"
        }
      }
    }
  }
});

const urgency = noulDecision.answers.is_urgent;
console.log("[noul]");
console.log({ type: urgency.type, probabilityOfYes: urgency.noul });

// 2. choice: 가장 적합한 항목과 각 항목의 확률을 반환합니다.
const choiceDecision = await openrouter.alpha.decisions.create({
  decisionsRequest: {
    model,
    state: "I was charged twice for my subscription. Please refund the duplicate payment.",
    questions: {
      department: {
        type: "choice",
        instructions: "Which team should handle this request?",
        criteria: {
          billing: "Payments, invoicing, refunds, or duplicate charges",
          technical: "Bugs, outages, or integrations",
          sales: "Pricing, upgrades, or new accounts"
        }
      }
    }
  }
});

const department = choiceDecision.answers.department;
console.log("\n[choice]");
console.log({
  type: department.type,
  selected: department.choice,
  probabilities: department.probabilities
});

// 3. score: 순서가 있는 기준 중 판단 위치를 숫자로 반환합니다.
const scoreDecision = await openrouter.alpha.decisions.create({
  decisionsRequest: {
    model,
    state: "This is the third time your service has failed. I am extremely angry!",
    questions: {
      frustration: {
        type: "score",
        instructions: "How frustrated is the customer?",
        criteria: ["Calm", "Frustrated", "Very angry"]
      }
    }
  }
});

const frustration = scoreDecision.answers.frustration;
console.log("\n[score]");
console.log({ type: frustration.type, score: frustration.score });
