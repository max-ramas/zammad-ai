import gradio as gr
import httpx

# Base URL für die API
API_BASE_URL = "http://localhost:8080"


async def process_ticket(text: str):
    """
    Verarbeitet einen Ticket-Text durch Triage und ggf. AI-Antwort.

    Returns:
        Tuple mit (Category, Action, Reasoning, Confidence, Answer)
    """
    if not text.strip():
        return "Keine Eingabe", "", "", "", "", []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            triage_response = await client.post(f"{API_BASE_URL}/api/v1/triage", json={"text": text})
            triage_response.raise_for_status()
            triage_data = triage_response.json()
        except httpx.ConnectError:
            return f"Verbindungsfehler: Backend läuft nicht auf {API_BASE_URL}", "", "", "", "", []
        except httpx.TimeoutException:
            return "Timeout: Triage dauert zu lange", "", "", "", "", []
        except httpx.HTTPStatusError as e:
            return f"HTTP-Fehler {e.response.status_code}: {e.response.text}", "", "", "", "", []
        except Exception as e:
            return f"Fehler bei Triage: {type(e).__name__}: {str(e)}", "", "", "", "", []

        triage_result = triage_data.get("triage", {})
        session_id = triage_data.get("id")

        category = triage_result.get("category", {}).get("name", "Unbekannt")
        action = triage_result.get("action", {}).get("name", "Unbekannt")
        reasoning = triage_result.get("reasoning", "")
        confidence = triage_result.get("confidence", 0.0)

        answer = ""
        answer_documents = []
        if str(action) == "KI_Antwort":
            try:
                answer_response = await client.post(
                    f"{API_BASE_URL}/api/v1/answer", json={"text": text, "id": session_id, "category": category}
                )
                answer_response.raise_for_status()
                json = answer_response.json()
                answer = json["response"]
                answer_documents = json.get("documents", [])

            except Exception as e:
                answer = f"Fehler bei Answer-Generierung: {str(e)}"

        confidence_str = f"{confidence * 100:.1f}%"

        return category, action, reasoning, confidence_str, answer, answer_documents


with gr.Blocks(title="Zammad AI Triage Demo") as demo:
    gr.Markdown("# Zammad AI Triage & Answer Demo")
    gr.Markdown("Geben Sie einen Ticket-Text ein, um die KI-gestützte Triage und Antwortgenerierung zu testen.")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Eingabe")
            input_text = gr.Textbox(label="Ticket-Text", placeholder="Geben Sie hier Ihre Anfrage ein...", lines=10)
            submit_btn = gr.Button("Absenden", variant="primary")

            gr.Markdown("### Beispiele")
            with gr.Row():
                gr.Button("MA_beantwortet", size="sm").click(
                    lambda: (
                        "Guten Tag, unter folgendem Link finden Sie alle Informationen rund um den internationalen Führerschein: Dort können Sie auch direkt online einen Antrag stellen. Alternativ können Sie einen Termin vereinbaren und sich den internationalen Führerschein Vorort ausstellen lassen: Mit freundlichen Grüßen"
                    ),
                    outputs=input_text,
                )
                gr.Button("Fragen", size="sm").click(
                    lambda: (
                        "Sehr geehrte Damen und Herren, wie im Anhang zu sehen ist habe ich eine Bestätigung der bestandenen Praxisprüfung erhalten, mit der ich aber anscheinend noch nicht fahren darf. Muss ich für die Prüfungsbescheinigung für begleitetes Fahren ein Termin ausmachen, weil alle anderen haben diese Bescheinigung eigentlich am Tag ihrer Prüfung direkt erhalten. Mit freundlichen Grüssen Straße  "
                    ),
                    outputs=input_text,
                )
            with gr.Row():
                gr.Button("Terminanfrage", size="sm").click(
                    lambda: (
                        "ISehr geehrten Damen und Herren ich möchte gerne einen Termin für den umtausch meiner Führerschein.Mit freundichen Grüßen"
                    ),
                    outputs=input_text,
                )
                gr.Button("Anfrage_Bearbeitungsstand", size="sm").click(
                    lambda: (
                        "Sehr geehrte Damen und Herren, bis wann ist denn mit der Bearbeitung des Umtausches zu rechnen?Ich würde gern im kommenden Urlaub einen gültigen Führerschein bei mir haben :) Danke und freundliche Grüße"
                    ),
                    outputs=input_text,
                )
            with gr.Row():
                gr.Button("Zuordnung nicht möglich", size="sm").click(
                    lambda: (
                        'Hallo, Ihre EMail mit dem Betreff "Führerschein " konnte leider nicht an einen oder mehrere Empfänger zugestellt werden. Die Nachricht hatte eine Größe von 14.99 MB, wir akzeptieren jedoch nur EMails mit einer Größe von bis zu 10 MB. Bitte reduzieren Sie die Größe Ihrer Nachricht und versuchen Sie es erneut. Vielen Dank für Ihr Verständnis. Mit freundlichen Grüßen Postmaster von dbszammad.muenchen.de '
                    ),
                    outputs=input_text,
                )
                gr.Button("Nachreichung", size="sm").click(
                    lambda: (
                        "Hallo wie telefonisch vereinbart sende ich Ihnen die Bestätigung des Zertifikates zu .Zu dem wollte ich mich nochmals entschuldigen mich so spät gemeldet zu haben da meine aktuelle Lebenssituation nicht auf dem graden weg ist Streitigkeiten im Elternhaus ist mein grösstes problem . Aktuell wohne ich nichtmehr bei meinen eltern sondern übernachte bei meiner Freundin ich habe leider sehr spät zugriff auf meine briefe erhalten und zudem hat es wirklich lange gedauert mit dem termin für das Gutachten.. wir haben uns geeinigt einmal die woche meine post abholen zu dürfen also .. Ich hoffe das ich mein Zertifikat schnellst möglich bekomme und ihnen das direkt zu senden kann. Denn der Führerschein ist lebensnotwendig für mich .. Mit freundlichen Grüßen"
                    ),
                    outputs=input_text,
                )

        with gr.Column():
            gr.Markdown("### Ergebnisse")
            category_output = gr.Textbox(label="Category", interactive=False)
            action_output = gr.Textbox(label="Action", interactive=False)
            confidence_output = gr.Textbox(label="Confidence", interactive=False)
            reasoning_output = gr.Textbox(label="Reasoning", interactive=False, lines=3)
            answer_output = gr.Textbox(label="KI-Antwort", interactive=False, lines=12)
            answer_documents_output = gr.Textbox(label="Answer Documents", interactive=False, lines=20)

    submit_btn.click(
        fn=process_ticket,
        inputs=[input_text],
        outputs=[category_output, action_output, reasoning_output, confidence_output, answer_output, answer_documents_output],
    )

    input_text.submit(
        fn=process_ticket, inputs=[input_text], outputs=[category_output, action_output, reasoning_output, confidence_output, answer_output]
    )

if __name__ == "__main__":
    demo.launch(server_name="localhost", server_port=7860)
