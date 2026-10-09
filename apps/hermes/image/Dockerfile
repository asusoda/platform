# The Hermes Agent image with the Platform MCP server set from the environment. Start command: gateway run.
# HERMES_IMAGE is a Hermes image the org built from github.com/NousResearch/hermes-agent. See ../README.md.
ARG HERMES_IMAGE
FROM ${HERMES_IMAGE}

COPY --chmod=0755 platform-config.sh /etc/cont-init.d/03-platform-config

CMD ["gateway", "run"]
