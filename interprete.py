import logging
import spacy
from transformers import pipeline
import sqlalchemy as db
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import tkinter as tk
from tkinter import scrolledtext, messagebox
from typing import Tuple, List, Optional, Dict
import configparser
import json
from datetime import datetime
import os

# Configurar logging
logging.basicConfig(
    filename='covid_query_app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_file: str = 'config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self) -> None:
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.create_default_config()

    def create_default_config(self) -> None:
        self.config['DATABASE'] = {
            'connection_string': 'sqlite:///health_data.db',
            'pool_size': '5',
            'max_overflow': '10'
        }
        self.config['NLP'] = {
            'spacy_model': 'en_core_web_sm',
            'confidence_threshold': '0.7'
        }
        with open(self.config_file, 'w') as f:
            self.config.write(f)

class DatabaseManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.engine = self._create_engine()
        self.SessionMaker = sessionmaker(bind=self.engine)
        self.query_cache = {}

    def _create_engine(self) -> db.Engine:
        try:
            return db.create_engine(
                self.config.config['DATABASE']['connection_string'],
                poolclass=QueuePool,
                pool_size=int(self.config.config['DATABASE']['pool_size']),
                max_overflow=int(self.config.config['DATABASE']['max_overflow'])
            )
        except Exception as e:
            logger.error(f"Error creating database engine: {e}")
            raise

    def execute_query(self, query: str, params: Dict) -> Optional[List]:
        cache_key = f"{query}_{json.dumps(params, sort_keys=True)}"
        
        if cache_key in self.query_cache:
            cache_time, results = self.query_cache[cache_key]
            if (datetime.now() - cache_time).seconds < 300:
                return results

        try:
            with self.SessionMaker() as session:
                result = session.execute(text(query), params)
                results = result.fetchall()
                self.query_cache[cache_key] = (datetime.now(), results)
                return results
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return None

class NLPProcessor:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.confidence_threshold = float(config.config['NLP']['confidence_threshold'])
        try:
            self.classifier = pipeline("text-classification", 
                                    model="distilbert-base-uncased-finetuned-sst-2-english")
            self.nlp = spacy.load(config.config['NLP']['spacy_model'])
        except Exception as e:
            logger.error(f"Error loading NLP models: {e}")
            raise

    def validate_query(self, query: str) -> bool:
        try:
            result = self.classifier(query)[0]
            return result['score'] > self.confidence_threshold
        except Exception as e:
            logger.error(f"Error validating query: {e}")
            return False

    def process_query(self, query: str) -> Tuple[str, Dict]:
        if not self.validate_query(query):
            return "", {}

        try:
            doc = self.nlp(query.lower())
            params = {}
            
            # Determinar el tipo de consulta y tabla base
            if "vacuna" in query:
                return self._process_vaccine_query(query, doc, params)
            elif "hospital" in query or "cama" in query:
                return self._process_hospital_query(query, doc, params)
            elif "prueba" in query or "test" in query:
                return self._process_test_query(query, doc, params)
            else:
                return self._process_cases_query(query, doc, params)
                
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return "", {}

    def _process_vaccine_query(self, query: str, doc, params: Dict) -> Tuple[str, Dict]:
        sql_query = """
            SELECT SUM(vacunaciones.personas_vacunadas) as resultado
            FROM vacunaciones 
            JOIN ubicaciones ON vacunaciones.ubicacion_id = ubicaciones.id 
            WHERE 1=1
        """
        
        # Procesar tipo de vacuna
        for vacuna in ['Pfizer', 'Moderna', 'Johnson', 'AstraZeneca']:
            if vacuna.lower() in query:
                params['tipo_vacuna'] = vacuna
                sql_query += " AND tipo_vacuna = :tipo_vacuna"
                break
        
        return self._add_common_filters(sql_query, doc, params)

    def _process_hospital_query(self, query: str, doc, params: Dict) -> Tuple[str, Dict]:
        sql_query = """
            SELECT 
                CASE 
                    WHEN :metric = 'disponibles' THEN SUM(camas_disponibles)
                    WHEN :metric = 'ocupadas' THEN SUM(camas_ocupadas)
                    ELSE SUM(camas_disponibles + camas_ocupadas)
                END as resultado
            FROM hospitalizaciones 
            JOIN ubicaciones ON hospitalizaciones.ubicacion_id = ubicaciones.id 
            WHERE 1=1
        """
        
        if "disponible" in query:
            params['metric'] = 'disponibles'
        elif "ocupada" in query:
            params['metric'] = 'ocupadas'
        else:
            params['metric'] = 'total'
            
        return self._add_common_filters(sql_query, doc, params)

    def _process_test_query(self, query: str, doc, params: Dict) -> Tuple[str, Dict]:
        sql_query = """
            SELECT 
                CASE 
                    WHEN :metric = 'positivas' THEN SUM(pruebas_positivas)
                    ELSE SUM(total_pruebas)
                END as resultado
            FROM pruebas 
            JOIN ubicaciones ON pruebas.ubicacion_id = ubicaciones.id 
            WHERE 1=1
        """
        
        if "positiva" in query:
            params['metric'] = 'positivas'
        else:
            params['metric'] = 'total'
            
        if "pcr" in query.lower():
            params['tipo_prueba'] = 'PCR'
            sql_query += " AND tipo_prueba = :tipo_prueba"
        elif "antígeno" in query.lower():
            params['tipo_prueba'] = 'Antígenos'
            sql_query += " AND tipo_prueba = :tipo_prueba"
            
        return self._add_common_filters(sql_query, doc, params)

    def _process_cases_query(self, query: str, doc, params: Dict) -> Tuple[str, Dict]:
        sql_query = """
            SELECT 
                CASE 
                    WHEN :metric = 'muertes' THEN SUM(muertes)
                    WHEN :metric = 'activos' THEN SUM(casos_activos)
                    WHEN :metric = 'recuperados' THEN SUM(casos_recuperados)
                    ELSE SUM(casos_confirmados)
                END as resultado
            FROM casos_covid 
            JOIN ubicaciones ON casos_covid.ubicacion_id = ubicaciones.id 
            WHERE 1=1
        """
        
        if "muerte" in query:
            params['metric'] = 'muertes'
        elif "activo" in query:
            params['metric'] = 'activos'
        elif "recuperado" in query:
            params['metric'] = 'recuperados'
        else:
            params['metric'] = 'confirmados'
            
        return self._add_common_filters(sql_query, doc, params)

    def _add_common_filters(self, sql_query: str, doc, params: Dict) -> Tuple[str, Dict]:
        for ent in doc.ents:
            if ent.label_ == "GPE":
                params['ubicacion'] = ent.text.title()
                sql_query += " AND ubicaciones.ciudad = :ubicacion"
            elif ent.label_ == "DATE":
                params['fecha'] = ent.text
                sql_query += " AND fecha LIKE :fecha"
            elif ent.label_ == "CARDINAL" and "último" in doc.text:
                params['dias'] = int(ent.text)
                sql_query += " AND fecha >= date('now', :dias || ' days')"
        
        return sql_query, params

class CovidQueryGUI:
    def __init__(self):
        self.config = ConfigManager()
        self.db_manager = DatabaseManager(self.config)
        self.nlp_processor = NLPProcessor(self.config)
        self.setup_gui()

    def setup_gui(self):
        self.window = tk.Tk()
        self.window.title("Sistema de Consultas COVID-19")
        self.window.geometry("800x600")

        main_frame = tk.Frame(self.window, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        query_frame = tk.LabelFrame(main_frame, text="Consulta", padx=10, pady=10)
        query_frame.pack(fill=tk.X, pady=(0, 10))

        self.query_entry = tk.Entry(query_frame, width=70)
        self.query_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        send_button = tk.Button(query_frame, text="Enviar", command=self.process_query)
        send_button.pack(side=tk.RIGHT)

        results_frame = tk.LabelFrame(main_frame, text="Resultados", padx=10, pady=10)
        results_frame.pack(fill=tk.BOTH, expand=True)

        self.results_text = scrolledtext.ScrolledText(
            results_frame, 
            wrap=tk.WORD, 
            width=70, 
            height=20
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

    def process_query(self):
        query = self.query_entry.get().strip()
        if not query:
            messagebox.showwarning("Advertencia", "Por favor ingrese una consulta")
            return

        try:
            sql_query, params = self.nlp_processor.process_query(query)
            if not sql_query:
                self.show_results("No pude interpretar tu consulta. ¿Podrías reformularla?")
                return

            results = self.db_manager.execute_query(sql_query, params)
            if results is None:
                self.show_results("Ocurrió un error al procesar tu consulta")
                return

            self.show_results(self.format_results(results))
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            self.show_results("Ocurrió un error inesperado")

    def format_results(self, results: List) -> str:
        if not results:
            return "No se encontraron resultados para tu consulta"
        
        formatted = "Resultados de la consulta:\n\n"
        for row in results:
            formatted += f"{row}\n"
        return formatted

    def show_results(self, text: str):
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)

    def run(self):
        try:
            self.window.mainloop()
        except Exception as e:
            logger.error(f"Error running application: {e}")
            raise

if __name__ == "__main__":
    try:
        app = CovidQueryGUI()
        app.run()
    except Exception as e:
        logger.critical(f"Application failed to start: {e}")
        messagebox.showerror(
            "Error", 
            "La aplicación no pudo iniciarse. Por favor revise los logs para más detalles."
        )