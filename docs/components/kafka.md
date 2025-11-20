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

## TLS / mTLS configuration

Kafka connections can be secured either via classic PEM files or via PKCS#12 blobs that are delivered through environment variables. The relevant settings live under `kafka.mtls` in `config.yaml` (or the corresponding `ZAMMAD_AI_KAFKA__MTLS__*` env vars).

| Setting                   | Description                                                                                                                          |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `ca_file`                 | Path to a CA bundle on disk that should be trusted for the broker certificate.                                                       |
| `ca_env_var`              | Name of an environment variable that contains the CA certificate text. The helper accepts raw PEM or base64-encoded PEM.             |
| `cert_file` / `key_file`  | Paths to the client certificate/key in PEM format. Use when files are available on the filesystem.                                   |
| `pkcs12_env_var`          | Name of an environment variable with a base64-encoded PKCS#12 archive holding client key, certificate, and optionally intermediates. |
| `pkcs12_password_env_var` | Optional env var name that contains the password for the PKCS#12 archive.                                                            |

When `pkcs12_env_var` is configured, the broker security layer decodes the secret in-memory, converts it to PEM, and feeds it into aiokafka's SSL context. The CA material is taken from `ca_file` and/or `ca_env_var`, so you can point to the CA that signs the Kafka cluster itself even if it is only available through secrets.
