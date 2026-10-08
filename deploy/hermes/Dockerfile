# Hermes Agent (Nous Research) as a Platform app: a Discord bot that uses the org's Platform tools over MCP.
# State (config, memories, sessions, skills) lives in /opt/data; mount a RunPod network volume there.
FROM nousresearch/hermes-agent:v2026.9.24

COPY --chmod=0755 platform-config.sh /etc/cont-init.d/03-platform-config

CMD ["gateway", "run"]
