ARG SDK_IMAGE=ariadne-mark:local
FROM ${SDK_IMAGE}
COPY --chown=10001:10001 app.py index.html catalog.json product.json /product/
WORKDIR /product
ENTRYPOINT ["python", "/product/app.py"]
