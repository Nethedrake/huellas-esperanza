import os
from typing import Literal, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
MASCOTAS_API = os.environ["MASCOTAS_API_URL"].rstrip("/")

app = FastAPI(
    title="API 2 - Adopciones | Huellas de Esperanza",
    description="Registra, consulta y gestiona las solicitudes de adopción. "
    "Se comunica con la API de Mascotas por HTTP/REST.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SolicitudIn(BaseModel):
    mascota_id: int
    nombre_solicitante: str
    email: str
    telefono: Optional[str] = None
    motivo: Optional[str] = None


# ---------- Comunicación con la API 1 ----------
def consultar_mascota(mascota_id: int) -> dict:
    try:
        r = httpx.get(f"{MASCOTAS_API}/mascotas/{mascota_id}", timeout=10)
    except httpx.RequestError:
        raise HTTPException(503, "La API de Mascotas no está disponible")
    if r.status_code == 404:
        raise HTTPException(404, "La mascota no existe")
    r.raise_for_status()
    return r.json()


def cambiar_estado_mascota(mascota_id: int, estado: str) -> None:
    try:
        r = httpx.patch(
            f"{MASCOTAS_API}/mascotas/{mascota_id}/estado",
            json={"estado": estado},
            timeout=10,
        )
    except httpx.RequestError:
        raise HTTPException(503, "La API de Mascotas no está disponible")
    r.raise_for_status()


def obtener_solicitud(solicitud_id: int) -> dict:
    res = supabase.table("solicitudes").select("*").eq("id", solicitud_id).execute()
    if not res.data:
        raise HTTPException(404, "Solicitud no encontrada")
    return res.data[0]


# ---------- Endpoints ----------
@app.get("/", tags=["General"])
def salud():
    return {"servicio": "api-adopciones", "estado": "ok"}


@app.post("/solicitudes", status_code=201, tags=["Solicitudes"])
def crear_solicitud(datos: SolicitudIn):
    mascota = consultar_mascota(datos.mascota_id)  # llamada a la API 1
    if mascota["estado"] != "disponible":
        raise HTTPException(
            409, f"La mascota no está disponible (estado: {mascota['estado']})"
        )
    res = supabase.table("solicitudes").insert(datos.model_dump()).execute()
    return res.data[0]


@app.get("/solicitudes", tags=["Solicitudes"])
def listar_solicitudes(
    estado: Optional[Literal["pendiente", "aprobada", "rechazada"]] = None,
    mascota_id: Optional[int] = None,
):
    consulta = supabase.table("solicitudes").select("*").order("id")
    if estado:
        consulta = consulta.eq("estado", estado)
    if mascota_id:
        consulta = consulta.eq("mascota_id", mascota_id)
    return consulta.execute().data


@app.get("/solicitudes/{solicitud_id}", tags=["Solicitudes"])
def ver_solicitud(solicitud_id: int):
    return obtener_solicitud(solicitud_id)


@app.patch("/solicitudes/{solicitud_id}/aprobar", tags=["Gestión"])
def aprobar_solicitud(solicitud_id: int):
    solicitud = obtener_solicitud(solicitud_id)
    if solicitud["estado"] != "pendiente":
        raise HTTPException(409, f"La solicitud ya está {solicitud['estado']}")

    # Regla: una mascota no puede tener dos adopciones aprobadas
    ya = (
        supabase.table("solicitudes")
        .select("id")
        .eq("mascota_id", solicitud["mascota_id"])
        .eq("estado", "aprobada")
        .execute()
    )
    if ya.data:
        raise HTTPException(409, "Esta mascota ya tiene una adopción aprobada")

    mascota = consultar_mascota(solicitud["mascota_id"])  # llamada a la API 1
    if mascota["estado"] == "adoptada":
        raise HTTPException(409, "La mascota ya fue adoptada")

    try:
        # El índice único parcial de la BD bloquea aprobaciones simultáneas
        res = (
            supabase.table("solicitudes")
            .update({"estado": "aprobada"})
            .eq("id", solicitud_id)
            .execute()
        )
    except Exception:
        raise HTTPException(409, "Esta mascota ya tiene una adopción aprobada")

    cambiar_estado_mascota(solicitud["mascota_id"], "adoptada")  # llamada a la API 1
    return res.data[0]


@app.patch("/solicitudes/{solicitud_id}/rechazar", tags=["Gestión"])
def rechazar_solicitud(solicitud_id: int):
    solicitud = obtener_solicitud(solicitud_id)
    if solicitud["estado"] != "pendiente":
        raise HTTPException(409, f"La solicitud ya está {solicitud['estado']}")
    res = (
        supabase.table("solicitudes")
        .update({"estado": "rechazada"})
        .eq("id", solicitud_id)
        .execute()
    )
    return res.data[0]