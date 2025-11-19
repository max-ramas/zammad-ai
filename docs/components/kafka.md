# Kafka / Message Broker

The system utilizes an Apache Kafka message broker to trigger its workflows.
The related Kafka topic is published by Zammad upon ticket creation or update events.
Our Zammad-AI service subscribes to this topic to process incoming tickets and generate AI-driven responses.

Events have the following structure:

```json
{
  "action": "created",
  "ticket": "3720",
  "status": "new",
  "statusId": "1",
  "anliegenart": "technischer Bürgersupport",
  "lhmExtId": ""
}
```

The structure is defined in the dbs/ticketing-eventing service and can be found in its [GitHub repository](https://github.com/it-at-m/dbs/blob/main/ticketing-eventing/handler-core/src/main/java/de/muenchen/oss/dbs/ticketing/eventing/handlercore/domain/model/Event.java).
