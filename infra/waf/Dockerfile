# WAF ModSecurity + CRS avec les regles RESILIENCE-ALPHA integrees.
# tzdata + TZ pour que nginx et ModSecurity horodatent en heure de Paris (sinon UTC).
FROM owasp/modsecurity-crs:nginx

ENV TZ=Europe/Paris
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/Europe/Paris /etc/localtime \
    && echo "Europe/Paris" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY custom-rules.conf /etc/modsecurity.d/owasp-crs/rules/RESILIENCE-ALPHA.conf
