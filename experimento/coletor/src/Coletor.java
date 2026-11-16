import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.PrintWriter;
import java.time.Duration;
import java.time.Instant;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.atomic.AtomicBoolean;

import org.apache.kafka.clients.consumer.CloseOptions;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRebalanceListener;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.CooperativeStickyAssignor;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.StickyAssignor;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.errors.WakeupException;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;

/**
 * Consumidor instrumentado. Traduz as notificações do cliente Kafka em eventos de posse,
 * conforme a seção 6 de notas/formalizacao.md.
 *
 * <p>Escreve um registro de eventos em CSV, uma linha por partição notificada, com o
 * instante do relógio monotônico tomado uma única vez no início de cada callback.
 * Callbacks com coleção vazia não geram linha:
 *
 * <pre>evento,trabalhador,particao,epoca,mono_ns,relogio_ns</pre>
 *
 * <p>Eventos: {@code atribuida} ({@code onPartitionsAssigned}), {@code revogada}
 * ({@code onPartitionsRevoked}), {@code perdida} ({@code onPartitionsLost}), e
 * {@code processo_inicio} / {@code processo_fim}, sem partição, para a conferência da base
 * de tempo. A época é {@code groupMetadata().generationId()}: geração do grupo no
 * protocolo clássico, época do membro no KIP-848. O orquestrador transforma esse registro
 * no histórico de seis colunas que o verificador lê.
 *
 * <p>Uso: {@code java -cp "out:lib/*" Coletor chave=valor ...}. Chaves obrigatórias:
 * {@code trabalhador}, {@code protocolo} (eager | cooperativo | kip848), {@code grupo},
 * {@code topico}, {@code saida}. Opcionais: {@code bootstrap} (localhost:9092),
 * {@code sessao_ms} (10000), {@code heartbeat_ms} (3000), {@code poll_ms} (500),
 * {@code trabalho_ms} (0, tempo simulado de processamento por registro).
 */
public final class Coletor {

    public static void main(String[] args) throws Exception {
        Map<String, String> arg = argumentos(args);
        String trabalhador = obrigatorio(arg, "trabalhador");
        String protocolo = obrigatorio(arg, "protocolo");
        String grupo = obrigatorio(arg, "grupo");
        String topico = obrigatorio(arg, "topico");
        String saida = obrigatorio(arg, "saida");
        String bootstrap = arg.getOrDefault("bootstrap", "localhost:9092");
        int sessaoMs = Integer.parseInt(arg.getOrDefault("sessao_ms", "10000"));
        int heartbeatMs = Integer.parseInt(arg.getOrDefault("heartbeat_ms", "3000"));
        int pollMs = Integer.parseInt(arg.getOrDefault("poll_ms", "500"));
        int trabalhoMs = Integer.parseInt(arg.getOrDefault("trabalho_ms", "0"));

        Registrador registrador = new Registrador(saida, trabalhador);
        Properties config = configuracao(protocolo, bootstrap, grupo, trabalhador, sessaoMs, heartbeatMs);
        KafkaConsumer<byte[], byte[]> consumidor = new KafkaConsumer<>(config);

        ConsumerRebalanceListener ouvinte = new ConsumerRebalanceListener() {
            @Override
            public void onPartitionsAssigned(Collection<TopicPartition> particoes) {
                registrador.evento("atribuida", particoes, epoca(consumidor));
            }

            @Override
            public void onPartitionsRevoked(Collection<TopicPartition> particoes) {
                registrador.evento("revogada", particoes, epoca(consumidor));
            }

            @Override
            public void onPartitionsLost(Collection<TopicPartition> particoes) {
                registrador.evento("perdida", particoes, epoca(consumidor));
            }
        };

        AtomicBoolean rodando = new AtomicBoolean(true);
        Thread principal = Thread.currentThread();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            rodando.set(false);
            consumidor.wakeup();
            try {
                principal.join(20_000);
            } catch (InterruptedException ignorada) {
                Thread.currentThread().interrupt();
            }
        }, "encerramento"));

        registrador.processo("processo_inicio");
        try {
            consumidor.subscribe(List.of(topico), ouvinte);
            while (rodando.get()) {
                ConsumerRecords<byte[], byte[]> registros = consumidor.poll(Duration.ofMillis(pollMs));
                if (trabalhoMs > 0) {
                    for (ConsumerRecord<byte[], byte[]> ignorado : registros) {
                        Thread.sleep(trabalhoMs);
                    }
                }
            }
        } catch (WakeupException encerrar) {
            // pedido de encerramento pelo gancho de desligamento
        } finally {
            // close() dispara onPartitionsRevoked (ou onPartitionsLost, se a geração já caiu)
            consumidor.close(CloseOptions.timeout(Duration.ofSeconds(10)));
            registrador.processo("processo_fim");
            registrador.close();
        }
    }

    private static int epoca(KafkaConsumer<?, ?> consumidor) {
        return consumidor.groupMetadata().generationId();
    }

    private static Properties configuracao(
            String protocolo, String bootstrap, String grupo, String trabalhador, int sessaoMs, int heartbeatMs) {
        Properties p = new Properties();
        p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrap);
        p.put(ConsumerConfig.GROUP_ID_CONFIG, grupo);
        p.put(ConsumerConfig.CLIENT_ID_CONFIG, trabalhador);
        p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class.getName());
        p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class.getName());
        p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "true");
        switch (protocolo) {
            case "eager" -> {
                p.put(ConsumerConfig.GROUP_PROTOCOL_CONFIG, "classic");
                p.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG, StickyAssignor.class.getName());
                p.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, String.valueOf(sessaoMs));
                p.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, String.valueOf(heartbeatMs));
            }
            case "cooperativo" -> {
                p.put(ConsumerConfig.GROUP_PROTOCOL_CONFIG, "classic");
                p.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG, CooperativeStickyAssignor.class.getName());
                p.put(ConsumerConfig.SESSION_TIMEOUT_MS_CONFIG, String.valueOf(sessaoMs));
                p.put(ConsumerConfig.HEARTBEAT_INTERVAL_MS_CONFIG, String.valueOf(heartbeatMs));
            }
            case "kip848" -> {
                // sessão, sinal de vida e atribuidor são do servidor neste protocolo
                p.put(ConsumerConfig.GROUP_PROTOCOL_CONFIG, "consumer");
                p.put(ConsumerConfig.GROUP_REMOTE_ASSIGNOR_CONFIG, "uniform");
            }
            default -> throw new IllegalArgumentException(
                    "protocolo desconhecido: " + protocolo + " (eager | cooperativo | kip848)");
        }
        return p;
    }

    private static Map<String, String> argumentos(String[] args) {
        Map<String, String> m = new HashMap<>();
        for (String a : args) {
            int i = a.indexOf('=');
            if (i <= 0) {
                throw new IllegalArgumentException("argumento fora do formato chave=valor: " + a);
            }
            m.put(a.substring(0, i), a.substring(i + 1));
        }
        return m;
    }

    private static String obrigatorio(Map<String, String> m, String chave) {
        String v = m.get(chave);
        if (v == null || v.isBlank()) {
            throw new IllegalArgumentException("argumento obrigatório ausente: " + chave);
        }
        return v;
    }

    /** Escreve o registro de eventos, uma linha por partição, com descarga a cada linha. */
    static final class Registrador implements AutoCloseable {
        private final PrintWriter saida;
        private final String trabalhador;

        Registrador(String caminho, String trabalhador) throws IOException {
            boolean novo = !new File(caminho).exists();
            this.saida = new PrintWriter(new FileWriter(caminho, true), true);
            this.trabalhador = trabalhador;
            if (novo) {
                saida.println("evento,trabalhador,particao,epoca,mono_ns,relogio_ns");
            }
        }

        /** Evento de posse, uma linha por partição. Callbacks com coleção vazia, que o
         *  protocolo cooperativo emite a cada rebalanceamento, não alteram a posse e não
         *  geram linha. */
        synchronized void evento(String evento, Collection<TopicPartition> particoes, int epoca) {
            if (particoes.isEmpty()) {
                return;
            }
            long[] t = instante();
            for (TopicPartition tp : particoes) {
                saida.println(evento + "," + trabalhador + "," + tp.topic() + "-" + tp.partition()
                        + "," + epoca + "," + t[0] + "," + t[1]);
            }
        }

        /** Evento do processo, sem partição, para a conferência da base de tempo. */
        synchronized void processo(String evento) {
            long[] t = instante();
            saida.println(evento + "," + trabalhador + ",,-1," + t[0] + "," + t[1]);
        }

        /** Par (monotônico, parede). O monotônico é o ponto médio de duas leituras que
         *  cercam a leitura do relógio de parede, para que os dois se refiram ao mesmo
         *  instante dentro de metade do intervalo entre as leituras. */
        private static long[] instante() {
            long antes = System.nanoTime();
            Instant agora = Instant.now();
            long depois = System.nanoTime();
            long relogio = agora.getEpochSecond() * 1_000_000_000L + agora.getNano();
            return new long[] {antes + (depois - antes) / 2, relogio};
        }

        @Override
        public void close() {
            saida.close();
        }
    }
}
