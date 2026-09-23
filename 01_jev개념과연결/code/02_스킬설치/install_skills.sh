#!/bin/bash
# Jev 스킬 설치 (skills.sh CLI). 기본은 '지금 폴더(프로젝트)'에만 설치한다. 전역 설치는 -g.
#   ./install_skills.sh            # 프로젝트 설치: .claude/skills · .agents/skills · skills/
#   ./install_skills.sh -g         # 전역 설치: ~/.claude/skills · ~/.codex/skills · ~/.openclaw/skills
# 두 가지 스킬
#   1) typesafe-ai (공식)      : 에이전트가 'Jev를 써서 코드를 만들 때' 문서·쿡북을 찾아 쓰는 스킬
#   2) jev-judgment (커뮤니티) : 에이전트가 '자기 판단에 Jev를 쓰는' 스킬 (묻기 전·위험 명령 전·실패 후)
set -e
SCOPE=${1:-}
npx -y skills add HyunjunJeon/jev-judgment -a claude-code codex openclaw -y $SCOPE
npx -y skills add typesafe-ai/skills --skill typesafe-ai -a claude-code codex openclaw -y $SCOPE
echo
echo "Claude Code는 플러그인으로도 설치할 수 있습니다:"
echo "  claude plugin marketplace add typesafe-ai/skills && claude plugin install typesafe@typesafe-ai"
echo
echo "설치 위치 확인:"
ls -d .claude/skills/* .agents/skills/* skills/* 2>/dev/null || true
