import os
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

app = FastAPI(
    title="API 1 - Mascotas | Huellas de Esperanza",
    description="Administra el registro, consulta y disponibilidad de las mascotas.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Estado = Literal["disponible", "en_proceso", "adoptada"]


class MascotaIn(BaseModel):
    nombre: str
    especie: str
    raza: Optional[str] = None
    edad_anios: Optional[int] = None
    descripcion: Optional[str] = None
    foto_url: Optional[str] = None


class EstadoIn(BaseModel):
    estado: Estado


@app.get("/", tags=["General"])
def salud():
    return {"servicio": "api-mascotas", "estado": "ok"}


@app.post("/mascotas", status_code=201, tags=["Mascotas"])
def crear_mascota(mascota: MascotaIn):
    res = supabase.table("mascotas").insert(mascota.model_dump()).execute()
    return res.data[0]


@app.get("/mascotas", tags=["Mascotas"])
def listar_mascotas(estado: Optional[Estado] = None):
    consulta = supabase.table("mascotas").select("*").order("id")
    if estado:
        consulta = consulta.eq("estado", estado)
    return consulta.execute().data


@app.get("/mascotas/{mascota_id}", tags=["Mascotas"])
def obtener_mascota(mascota_id: int):
    res = supabase.table("mascotas").select("*").eq("id", mascota_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return res.data[0]


@app.put("/mascotas/{mascota_id}", tags=["Mascotas"])
def actualizar_mascota(mascota_id: int, mascota: MascotaIn):
    res = (
        supabase.table("mascotas")
        .update(mascota.model_dump())
        .eq("id", mascota_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return res.data[0]


@app.patch("/mascotas/{mascota_id}/estado", tags=["Disponibilidad"])
def cambiar_estado(mascota_id: int, datos: EstadoIn):
    res = (
        supabase.table("mascotas")
        .update({"estado": datos.estado})
        .eq("id", mascota_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return res.data[0]