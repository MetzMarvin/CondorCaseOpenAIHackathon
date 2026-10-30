# Hackathon-Dokumentation

- [Subsystems and interface contracts](architecture/subsystems-and-contracts.md): drei Entwicklungsbereiche, synchrone KI-Verarbeitung, gemeinsame Datenmodelle, API-Verträge und Ereignisse für die 3-Stunden-Demo.

- [Hackathon-Plan](planning/hackathon-plan.md): Problemstatement, Ziele, MVP, Architektur, Salesforce-Dummy, Datenkonzept, Kennzahlen und Demo-Ablauf.
- [Visueller Plan](planning/visual-plan.html): interaktive Übersicht mit „Einfacher Fall“, „Beleg fehlt“, „Schwerwiegender Fall“ und „Verärgert, aber klar“. KI stellt klare Rückfragen selbst und bearbeitet unterstützte Fälle automatisch. Menschen übernehmen bei Fähigkeits-/Befugnisgrenzen oder schwerwiegenden Sachverhalten. Die Sentimentanalyse der Kundentexte unterstützt Tonalität und Priorisierung; Stimmung allein löst keine Übergabe aus.
- [Editierbare Visualisierungsquelle](planning/visual-plan.fragment.html): ursprüngliches HTML-Fragment für spätere Änderungen; die direkt öffnbare Version ist `visual-plan.html`.

- [Hackathon-Briefing (PDF)](reference/Customer_Care_Hackaton_AF_30OCT26.pdf): bereitgestellte Aufgabenstellung.
- [Recherche zu Beschwerdedatensätzen](research/airline-complaint-datasets.md): Datenquellen und fachliche Grundlagen.
- [Datenauswahl für schnelle Mocks und Tests](research/mock-dataset-selection.md): empfohlene Kombination aus Airline-Testdaten und deutsch-/englischen Tickets, Anpassung durch einen Agenten und Start mit 30 Prüffällen.

## Öffnen

`visual-plan.html` direkt im Browser öffnen. Es sind kein Build, keine Installation und kein Anwendungsserver erforderlich. Auf macOS vom Repository-Hauptverzeichnis aus:

```sh
open docs/planning/visual-plan.html
```

Die Visualisierung erklärt den geplanten Ablauf und ist keine implementierte Ticketanwendung. Die 3.000 synthetischen Fälle sind im Plan spezifiziert und noch nicht erzeugt.
