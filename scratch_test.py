from src.api_stub.runner import run_turn
import time

res = run_turn(
    session_id=None,
    user_text="Generate a premium creative for Tesco with packshot.",
    attachments=[],
    ui_context={"selected_formats": ["1080x1080", "1080x1920"]},
    title_if_new="Tesco demo"
)
print(res)
time.sleep(0.5)  # Allow LangSmith background thread to flush before exit
