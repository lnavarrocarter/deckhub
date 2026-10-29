"""Editor mínimo de archivos INI que conserva el resto del archivo tal cual.

configparser no sirve aquí: cambia mayúsculas, pierde comentarios y no admite
claves repetidas (PCSX2) ni claves con barras invertidas (Qt).
"""
import shutil
from pathlib import Path


class Ini:
    def __init__(self, path, sep=" = "):
        self.path, self.sep = Path(path), sep
        self.sections = [[None, []]]  # [nombre, líneas]
        if self.path.exists():
            for line in self.path.read_text(errors="replace").splitlines():
                s = line.strip()
                if s.startswith("[") and s.endswith("]"):
                    self.sections.append([s[1:-1], []])
                else:
                    self.sections[-1][1].append(line)

    def _section(self, name):
        for sec in self.sections:
            if sec[0] == name:
                return sec[1]
        self.sections.append([name, []])
        return self.sections[-1][1]

    @staticmethod
    def _key(line):
        return line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith((";", "#")) else None

    def get(self, section, key):
        for line in self._section(section):
            if self._key(line) == key:
                return line.split("=", 1)[1].strip()
        return None

    def remove(self, section, predicate):
        lines = self._section(section)
        lines[:] = [l for l in lines if not (self._key(l) is not None and predicate(self._key(l)))]

    def set(self, section, key, value):
        lines = self._section(section)
        new = f"{key}{self.sep}{value}"
        for i, line in enumerate(lines):
            if self._key(line) == key:
                lines[i] = new
                return
        self._insert(lines, [new])

    def set_list(self, section, key, values):
        """Clave repetida una vez por valor (formato de listas de PCSX2)."""
        self.remove(section, lambda k: k == key)
        self._insert(self._section(section), [f"{key}{self.sep}{v}" for v in values])

    def add(self, section, pairs):
        self._insert(self._section(section), [f"{k}{self.sep}{v}" for k, v in pairs])

    @staticmethod
    def _insert(lines, new):
        # Antes de las líneas en blanco finales de la sección, para mantener el formato.
        i = len(lines)
        while i > 0 and not lines[i - 1].strip():
            i -= 1
        lines[i:i] = new

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.path.with_name(self.path.name + ".deckhub.bak")
        if self.path.exists() and not backup.exists():
            shutil.copy2(self.path, backup)  # copia del original, una sola vez
        out = []
        for name, lines in self.sections:
            if name is not None:
                out.append(f"[{name}]")
            out.extend(lines)
        self.path.write_text("\n".join(out).strip("\n") + "\n")
