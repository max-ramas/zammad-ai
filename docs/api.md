# REST API Reference

The Zammad-AI service provides a REST API for synchronous triage and processing. This is useful for testing, manual trigger, or integration with systems that do not use Kafka.

## Base URL

By default, the API is available at `http://localhost:8080/api/v1`.

## Endpoints

### Triage

Analyze text and determine the best action.

- **URL**: `/triage`
- **Method**: `POST`
- **Request Body**: `TriageInput`

| Field        | Type                | Description                                                                     |
| :----------- | :------------------ | :------------------------------------------------------------------------------ |
| `text`       | `string`            | The text to be analyzed (e.g., ticket content).                                 |
| `session_id` | `string` (optional) | A unique identifier for the request. If not provided, a UUID will be generated. |

- **Response Body**: `TriageOutput`

| Field        | Type     | Description                       |
| :----------- | :------- | :-------------------------------- |
| `session_id` | `string` | The request ID.                   |
| `triage`     | `object` | The result of the triage process. |

#### Triage Result Object

| Field        | Type     | Description                                        |
| :----------- | :------- | :------------------------------------------------- |
| `category`   | `object` | The determined category (ID and name).             |
| `action`     | `object` | The determined action (ID, name, and description). |
| `reasoning`  | `string` | The LLM's reasoning for the categorization.        |
| `confidence` | `float`  | Confidence score between 0 and 1.                  |

- **Example Request**:

```json
{
  "text": "My email is not working and I cannot see any new messages.",
  "session_id": "req-123"
}
```

- **Example Response**:

```json
{
  "session_id": "req-123",
  "triage": {
    "category": { "id": 1, "name": "Technical Support" },
    "action": {
      "id": 2,
      "name": "Auto-Reply",
      "description": "Send standard help article link."
    },
    "reasoning": "The user mentions email issues which typically falls under technical support.",
    "confidence": 0.95
  }
}
```

## Internal Endpoints

### Health Check

Check the status of the service.

- **URL**: `/health`
- **Method**: `GET`
- **Response**: `{"status": "healthy"}`
