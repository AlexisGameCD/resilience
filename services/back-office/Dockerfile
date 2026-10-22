# back-office : page d'administration gardee par reconnaissance faciale + mot de passe.
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY html/ /usr/share/nginx/html/

EXPOSE 80
