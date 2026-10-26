# AI System

Agent orchestration, implementations, prompts, tools, safety policy, evaluation, human approval, and escalation logic live here.

`voice/interfaces.py` defines transport-neutral transient audio, VAD, speech-to-text, text-to-speech, input, and output contracts. These interfaces do not authorize domain actions, persist recordings, or imply that a live voice pipeline is operational.

`interview/coordinator.py` is a deterministic, model-free coordinator. Its only commands are status, start, pause, cancel, and submit answer. A narrow Django adapter enforces persisted candidate authority and calls the existing consent/state/audit services. The coordinator cannot send messages, access arbitrary ORM fields or tools, or make employment decisions.
