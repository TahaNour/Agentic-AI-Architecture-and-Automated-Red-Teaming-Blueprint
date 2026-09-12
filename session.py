"""
Contexte de session : identite de l'employe connecte.

Point critique de design : cette identite est etablie par le systeme
d'authentification (ici simule), JAMAIS par le contenu de la conversation.
Un utilisateur qui ecrit "je suis l'employe E1087" ne doit pas changer
cette valeur -- c'est precisement ce que les attaques ASI02 tenteront.

Les outils Ops lisent CURRENT_SESSION, pas ce que dit le prompt.
"""


class SessionContext:
    def __init__(self, employee_id: str, full_name: str):
        self.employee_id = employee_id
        self.full_name = full_name

    def __repr__(self):
        return f"<Session {self.employee_id} / {self.full_name}>"


# session par defaut : Sarah Ben Ali, Marketing
# (definie au demarrage par main.py, immuable pendant la conversation)
CURRENT_SESSION = SessionContext("E1042", "Sarah Ben Ali")


def get_session() -> SessionContext:
    return CURRENT_SESSION


def set_session(employee_id: str, full_name: str):
    """Appelee UNIQUEMENT par le point d'entree du systeme (main.py),
    jamais par un agent ni par un outil."""
    global CURRENT_SESSION
    CURRENT_SESSION = SessionContext(employee_id, full_name)