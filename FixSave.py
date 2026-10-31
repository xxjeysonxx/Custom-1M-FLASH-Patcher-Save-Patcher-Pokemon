#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FixSave.py - Arregla un .sav de Pokemon gen 3 para un cartucho bootleg de 64 KB.

Elige el .sav, pulsa APLICAR FIX y copia el fichero resultante a la SD.
Vale igual para volcados del cartucho, saves de emulador o saves tocados con PKHeX.

Uso:  doble clic, o  python FixSave.py
"""

# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import struct

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TK_OK = True
except ImportError:
    tk = ttk = filedialog = messagebox = None
    TK_OK = False

SECTOR = 0x1000
DATA = 0xFF4
MAGIC = 0x08012025
OUT_SIZE = 0x20000
MIN_COUNTER = 1000

CHARSET = {}
for _i in range(10):
    CHARSET[0xA1 + _i] = str(_i)
for _i in range(26):
    CHARSET[0xBB + _i] = chr(ord("A") + _i)
    CHARSET[0xD5 + _i] = chr(ord("a") + _i)
CHARSET.update({
    0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-", 0xB0: ".",
    0xB1: '"', 0xB2: '"', 0xB3: "'", 0xB4: "'",
    0xB8: ",", 0xB9: ",", 0xBA: "/", 0x5B: "(", 0x5D: ")",
})


# --------------------------------------------------------------------------
# nucleo
# --------------------------------------------------------------------------

def checksum(blk):
    c = 0
    for i in range(0, DATA, 4):
        c = (c + struct.unpack_from("<I", blk, i)[0]) & 0xFFFFFFFF
    return ((c >> 16) + (c & 0xFFFF)) & 0xFFFF


def read_sectors(data):
    out = []
    for off in range(0, len(data) - SECTOR + 1, SECTOR):
        blk = data[off:off + SECTOR]
        sid, cks, sec, cnt = struct.unpack_from("<HHII", blk, DATA)
        ok = (sec == MAGIC and cks == checksum(blk) and sid < 32)
        out.append({"off": off, "id": sid, "cks": cks, "sec": sec,
                    "counter": cnt, "ok": ok, "blk": blk})
    return out


def find_slots(sectors):
    by_counter = {}
    for s in sectors:
        if s["ok"]:
            by_counter.setdefault(s["counter"], {})[s["id"]] = s
    slots = []
    for cnt, ids in by_counter.items():
        have = sorted(ids)
        slots.append({"counter": cnt, "ids": have,
                      "complete": have == list(range(14)),
                      "sectors": ids})
    slots.sort(key=lambda x: x["counter"], reverse=True)
    return slots


def assemble(slot_sectors):
    return b"".join(slot_sectors[i]["blk"][:DATA] for i in range(14))


def decode_name(raw):
    out = []
    for c in raw:
        if c in (0x00, 0xFF):
            break
        out.append(CHARSET.get(c, "?"))
    return "".join(out) or "(sin nombre)"


def trainer_info(buf):
    tid = struct.unpack_from("<I", buf, 0x0A)[0]
    hours = struct.unpack_from("<H", buf, 0x0E)[0]
    return {
        "name": decode_name(buf[0:8]),
        "gender": "chica" if buf[8] == 1 else "chico",
        "tid": tid % 65536,
        "sid": tid >> 16,
        "time": "%d h %02d m %02d s" % (hours, buf[0x10], buf[0x11]),
    }


def analyze(path):
    data = open(path, "rb").read()
    sectors = read_sectors(data)
    slots = find_slots(sectors)
    complete = [s for s in slots if s["complete"]]
    info = {"data": data, "sectors": sectors, "slots": slots,
            "complete": complete, "size": len(data)}

    # Nombre de entrenador de CADA ranura completa. Ver dos nombres distintos
    # es la senal de que el fichero trae dos estados (PKHeX o emulador) y de
    # cual de los dos se va a usar.
    for sl in slots:
        sl["trainer"] = None
        if sl["complete"]:
            try:
                sl["trainer"] = trainer_info(assemble(sl["sectors"]))
            except Exception:
                pass

    chosen, filled = choose_sectors(sectors)
    info["chosen"] = chosen
    info["filled"] = filled
    info["counter"] = 0
    if chosen:
        info["counter"] = max(s["counter"] for s in chosen.values())
        try:
            info["trainer"] = trainer_info(assemble(chosen))
        except Exception:
            info["trainer"] = None
    return info


def build(slot_sectors, counter):
    """Devuelve 128 KB: ranura valida en la mitad baja, 0xFF en la alta.

    La segunda mitad NO es una copia de la primera. En un chip de 64 KB el
    comando de banco se ignora, asi que GodMode9i escribe los 128 KB sobre los
    mismos 64 KB fisicos: el segundo pase reprograma las mismas celdas. Como
    programar solo puede bajar bits a 0, escribir 0xFF no cambia nada
    (0xFF AND x == x) y el segundo pase resulta inofensivo.

    Duplicar la mitad funcionaba para GodMode9i, pero dejaba DOS ranuras con el
    MISMO contador. Un save real de 128 KB siempre tiene contadores distintos
    en cada ranura, y PKHeX se apoya en eso: al reescribir el fichero colocaba
    los bloques mal y el nombre del entrenador acababa en blanco.
    """
    low = bytearray(b"\xFF" * 0x10000)
    for sid in range(14):
        phys = ((sid + counter) % 14) + 14 * (counter & 1)
        blk = bytearray(slot_sectors[sid]["blk"])
        struct.pack_into("<HHII", blk, DATA, sid, checksum(blk), MAGIC, counter)
        low[phys * SECTOR:(phys + 1) * SECTOR] = blk
    return bytes(low) + b"\xFF" * 0x10000


def verify(out_data, counter):
    secs = read_sectors(out_data)
    slots = find_slots(secs)
    good = [s for s in slots if s["complete"] and s["counter"] == counter]
    high_blank = out_data[0x10000:] == b"\xFF" * 0x10000
    return bool(good), high_blank, len([s for s in secs if s["ok"]])


def out_counter(counter):
    """Contador con el que se escribe: par y nunca por debajo de MIN_COUNTER.

    Par porque la ranura tiene que caer en la mitad baja (0x0000-0xDFFF), que es
    la unica que existe fisicamente en un chip de 64 KB.
    """
    c = max(counter, MIN_COUNTER)
    if c & 1:
        c += 1
    return c


def choose_sectors(sectors):
    """Elige que sectores van al fichero de salida.

    Devuelve (dict id->sector, ids_rellenados) o (None, ids_que_faltan).

    Primero busca una ranura completa y se queda con la del contador mas alto,
    que es la que el juego usaria. Si no hay ninguna completa, fusiona: para
    cada bloque toma la copia valida mas reciente de todo el fichero. Eso es lo
    que hace falta en un cartucho de 64 KB, donde las dos ranuras se solapan y
    un guardado interrumpido puede dejar a cada una sin bloques distintos.

    Los bloques de caja ausentes se rellenan con un sector a cero (= 30 huecos
    vacios, checksum 0x0000), que es justo como los ve la consola. Si falta
    entrenador o equipo (ids 0-4) no se rellena nada: ahi no hay partida que
    rescatar y inventarla seria fabricar un fichero falso.
    """
    by_counter = {}
    for s in sectors:
        if s["ok"]:
            by_counter.setdefault(s["counter"], {})[s["id"]] = s

    complete = [c for c, ids in by_counter.items() if sorted(ids) == list(range(14))]
    if complete:
        return dict(by_counter[max(complete)]), []

    merged = {}
    for s in sectors:
        if not s["ok"] or s["id"] >= 14:
            continue
        cur = merged.get(s["id"])
        if cur is None or s["counter"] > cur["counter"]:
            merged[s["id"]] = s

    missing = [i for i in range(14) if i not in merged]
    if any(i < 5 for i in missing):
        return None, missing

    for i in missing:
        merged[i] = {"blk": bytes(SECTOR), "counter": 0, "id": i, "ok": True}
    return merged, missing


# --------------------------------------------------------------------------
# interfaz
# --------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.path = None
        self.info = None

        root.title("FixSave - Pokemon gen 3 para cartucho de 64 KB")
        root.geometry("720x640")
        root.minsize(640, 560)

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        # --- fichero
        top = ttk.Frame(root, padding=(12, 12, 12, 6))
        top.pack(fill="x")
        ttk.Label(top, text="1. Elige el .sav", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        row = ttk.Frame(top)
        row.pack(fill="x", pady=(4, 0))
        self.var_path = tk.StringVar(value="(ningun fichero)")
        entry = ttk.Entry(row, textvariable=self.var_path, state="readonly")
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Buscar...", command=self.pick).pack(side="left", padx=(6, 0))

        # --- diagnostico
        box1 = ttk.LabelFrame(root, text="Diagnostico", padding=8)
        box1.pack(fill="both", expand=True, padx=12, pady=6)
        self.txt_diag = tk.Text(box1, height=9, wrap="none",
                                font=("Consolas", 9), relief="flat",
                                bg="#1e1e1e", fg="#d4d4d4",
                                insertbackground="#d4d4d4")
        self.txt_diag.pack(fill="both", expand=True)
        self.txt_diag.configure(state="disabled")

        # --- accion
        mid = ttk.Frame(root, padding=(12, 2, 12, 6))
        mid.pack(fill="x")
        self.btn_fix = tk.Button(mid, text="2.  APLICAR FIX", height=2,
                                 font=("Segoe UI", 11, "bold"),
                                 command=self.fix, state="disabled",
                                 bg="#1f6f3f", fg="white",
                                 activebackground="#2a8a50", activeforeground="white",
                                 relief="flat", cursor="hand2")
        self.btn_fix.pack(fill="x")

        # --- resultado
        box2 = ttk.LabelFrame(root, text="Resultado", padding=8)
        box2.pack(fill="both", expand=True, padx=12, pady=6)
        self.txt_out = tk.Text(box2, height=7, wrap="word",
                               font=("Consolas", 9), relief="flat",
                               bg="#1e1e1e", fg="#d4d4d4")
        self.txt_out.pack(fill="both", expand=True)
        self.txt_out.configure(state="disabled")

        foot = ttk.Label(root, padding=(12, 0, 12, 10),
                         text="Orden correcto: volcar  ->  editar en PKHeX  ->  "
                              "APLICAR FIX  ->  inyectar el *_cartucho.sav.  "
                              "El original nunca se modifica.")
        foot.pack(fill="x")

    # --------------------------------------------------------------
    def log_diag(self, text):
        self.txt_diag.configure(state="normal")
        self.txt_diag.delete("1.0", "end")
        self.txt_diag.insert("1.0", text)
        self.txt_diag.configure(state="disabled")

    def log_out(self, text):
        self.txt_out.configure(state="normal")
        self.txt_out.delete("1.0", "end")
        self.txt_out.insert("1.0", text)
        self.txt_out.configure(state="disabled")

    def pick(self):
        path = filedialog.askopenfilename(
            title="Elige el .sav",
            filetypes=[("Save de Game Boy Advance", "*.sav"), ("Todos", "*.*")])
        if not path:
            return
        self.path = path
        self.var_path.set(path)
        self.btn_fix.configure(state="disabled")
        self.log_out("")
        self.analyse()

    def analyse(self):
        try:
            info = analyze(self.path)
        except Exception as exc:
            self.log_diag("ERROR leyendo el fichero:\n%s" % exc)
            messagebox.showerror("Error", "No se pudo leer el fichero:\n%s" % exc)
            return

        self.info = info
        lines = []
        lines.append("Fichero : %s" % os.path.basename(self.path))
        lines.append("Tamano  : %d bytes (0x%X)" % (info["size"], info["size"]))
        valid = len([s for s in info["sectors"] if s["ok"]])
        lines.append("Sectores: %d leidos, %d validos" %
                     (len(info["sectors"]), valid))
        lines.append("")

        if not info["sectors"] or valid == 0:
            lines.append("No hay ningun sector con firma 0x08012025 + checksum correcto.")
            lines.append("Esto no parece un save de gen 3 en flash.")
            self.log_diag("\n".join(lines))
            messagebox.showwarning("Save no reconocido",
                                   "El fichero no parece un save de Pokemon gen 3.")
            return

        lines.append("Ranuras encontradas:")
        for sl in info["slots"]:
            name = sl["trainer"]["name"] if sl["trainer"] else "-"
            lines.append("  contador %-9d %2d/14  %-10s  %s" % (
                sl["counter"], len(sl["ids"]),
                "COMPLETA" if sl["complete"] else "incompleta", name))
        lines.append("")

        if not info["chosen"]:
            falt = ", ".join(str(i) for i in info["filled"]) or "?"
            lines.append("No queda partida recuperable.")
            lines.append("Faltan bloques criticos: %s" % falt)
            lines.append("")
            lines.append("Los bloques 0-4 son entrenador, equipo y flags.")
            lines.append("Sin ellos no hay nada que rescatar.")
            self.log_diag("\n".join(lines))
            messagebox.showwarning(
                "Sin partida recuperable",
                "Faltan bloques criticos (%s).\n"
                "No se puede reconstruir la partida." % falt)
            return

        t = info["trainer"]
        lines.append("Ranura usada : contador %d" % info["counter"])
        if t:
            lines.append("Entrenador   : %s (%s)  TID %d / %d" %
                         (t["name"], t["gender"], t["tid"], t["sid"]))
            lines.append("Tiempo       : %s" % t["time"])
        if info["filled"]:
            lines.append("")
            lines.append("Bloques ausentes, rellenados como cajas vacias: %s" %
                         ", ".join(str(i) for i in info["filled"]))
        lines.append("")
        lines.append("Listo para aplicar el fix.")
        self.log_diag("\n".join(lines))
        self.btn_fix.configure(state="normal")

    def fix(self):
        if not self.info or not self.info["chosen"]:
            return
        counter = out_counter(self.info["counter"])

        try:
            out = build(self.info["chosen"], counter)
        except Exception as exc:
            messagebox.showerror("Error", "No se pudo construir el save:\n%s" % exc)
            return

        base = os.path.splitext(self.path)[0]
        dest = base + "_cartucho.sav"
        try:
            with open(dest, "wb") as f:
                f.write(out)
        except Exception as exc:
            messagebox.showerror("Error", "No se pudo escribir:\n%s" % exc)
            return

        good, high_blank, nvalid = verify(out, counter)
        t = trainer_info(assemble(self.info["chosen"]))
        lines = []
        lines.append("Escrito: %s" % dest)
        lines.append("Tamano : %d bytes (0x%X)" % (len(out), len(out)))
        lines.append("Segunda mitad en blanco: %s" % ("si" if high_blank else "NO"))
        lines.append("Ranura completa contador %d: %s" % (counter, "si" if good else "NO"))
        lines.append("Sectores validos: %d" % nvalid)
        lines.append("Entrenador: %s - %s" % (t["name"], t["time"]))
        self.log_out("\n".join(lines))

        if not t["name"] or t["name"] == "(sin nombre)":
            messagebox.showerror(
                "Nombre vacio",
                "El nombre del entrenador sale en blanco: el save de origen\n"
                "no tiene el bloque 0 (Trainer Info) en condiciones.\n"
                "No lo inyectes, no arrancaria.")
            return

        if not good or not high_blank:
            messagebox.showwarning("Revisar", "La salida no valida del todo. "
                                              "Mira el panel de resultado.")
            return
        self.btn_fix.configure(state="disabled")
        messagebox.showinfo("Hecho",
                            "Save listo:\n%s\n\nNombre: %s\n\n"
                            "Copialo a la SD y usalo como save del cartucho."
                            % (dest, t["name"]))


app = None


def main():
    global app
    if not TK_OK:
        raise SystemExit(
            "Este Python no trae tkinter.\n"
            "Prueba con otro interprete, por ejemplo:  py FixSave.py")
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
