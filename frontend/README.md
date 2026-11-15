# Frontend de TerraShift

Página estática (HTML, CSS y JavaScript sin dependencias ni paso de compilación). Se publica con GitHub Pages
desde la carpeta `frontend/`.

## Cómo funciona

1. Consulta la API del servidor (`apiBase` en `config.js`).
2. Si la zona no tiene datos todavía, muestra las estrategias con un aviso.
3. Si el servidor no responde (por ejemplo, un filtro de red lo bloquea), muestra la **copia de respaldo**
   `data/snapshot.json` y lo indica con la etiqueta "Datos de respaldo".

## Probar en local

```bash
cd frontend
python3 -m http.server 8000
# abrir http://localhost:8000
```

`http://localhost:8000` y `http://localhost:5500` ya están permitidos por el CORS del backend.

## Actualizar la copia de respaldo

Cuando haya resultados reales en el servidor:

```bash
curl -s "https://34-56-56-213.sslip.io/api/v1/strategies/compare?zone=piloto" > frontend/data/snapshot.json
```

Hacer commit del archivo. Al subirlo a `main`, la página se vuelve a publicar sola.

## Si cambia la dirección del servidor

- Editar `apiBase` en `config.js`.
- En el servidor, definir la variable `CORS_ALLOWED_ORIGINS` con el origen de la página
  (por defecto `https://rrodrovan.github.io`).
