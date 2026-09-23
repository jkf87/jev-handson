// OpenClaw 플러그인 진입점. 판정·정책은 lib/에 있어서 OpenClaw 없이도 시험할 수 있다.
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { registerJevRouter } from "./lib/plugin.js";

export default definePluginEntry({
  id: "jev-router",
  name: "Jev Router",
  description: "메시지마다 Jev에 한 번 물어 스팸·되묻기·대화·작업으로 나누고, 모델 호출 전에 처리한다.",
  register(api) {
    registerJevRouter(api);
  },
});
