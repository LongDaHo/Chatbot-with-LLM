# Install grafana-prometheus
```shell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install monitor-stack prometheus-community/kube-prometheus-stack --values grafana-prometheus.yaml -n observability 
```


# Install loki
```shell
helm repo add grafana https://grafana.github.io/helm-charts
helm install -f loki.yaml loki grafana/loki-stack -n observability
```

# Install tempo
```shell
helm install tempo grafana/tempo -f tempo.yaml -n observability
```

# Install open-telemetry collector
```shell
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm install opentelemetry-collector open-telemetry/opentelemetry-collector -f collector.yaml -n observability
```




