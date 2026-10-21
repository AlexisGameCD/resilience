# Grafana avec provisioning et dashboards integres.
# Les dashboards sont copies dans /etc/grafana/dashboards (hors du volume grafana-data
# monte sur /var/lib/grafana), pour ne jamais etre masques par un volume persistant.
FROM grafana/grafana:11.2.0
COPY provisioning/ /etc/grafana/provisioning/
COPY dashboards_json/ /etc/grafana/dashboards/
