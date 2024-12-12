from __future__ import annotations

import logging
from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai


load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("my-worker")
logger.setLevel(logging.INFO)


async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()

    run_multimodal_agent(ctx, participant)

    logger.info("agent started")


def run_multimodal_agent(ctx: JobContext, participant: rtc.Participant):
    logger.info("starting multimodal agent")

    model = openai.realtime.RealtimeModel(
        instructions=(
            "Saluda diciendo tu nombre el cual es SOPHIA, luego presentas quien eres y di Bienvenido al Experience Operacion Center"
            " Eres la Inteligencia artificial de la empresa TXDX SECURE"
            "Tu funcion es atender a los clientes que hagan una llamada para monitorear sus equipos, resolver dudas, etc."
            "TXDXSECURE es una empresa dedicada a redes y ciberseguridad "
            "Te haran preguntas de ciberseguridad asi que preparate para eso, si hay algun dato sobre la empresa que no sepas, inventalo"
        ),
        modalities=["audio", "text"],
        model=("gpt-4o-realtime-preview-2024-10-01"),
        voice="sage"
    )
    assistant = MultimodalAgent(model=model)
    assistant.start(ctx.room, participant)

    session = model.sessions[0]
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content="Please begin the interaction with the user in a manner consistent with your instructions.",
        )
    )
    session.response.create()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )

