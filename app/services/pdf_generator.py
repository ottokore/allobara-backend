# backend/app/services/pdf_generator.py
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from io import BytesIO
import logging
import os

logger = logging.getLogger(__name__)

class QuotePDFGenerator:
    """
    Générateur de PDF professionnels pour les demandes de devis AlloBara
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Configuration des styles personnalisés"""
        
        if 'MainTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='MainTitle',
                parent=self.styles['Title'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#F78A1C'),
                fontName='Helvetica-Bold'
            ))
        
        if 'SubTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SubTitle',
                parent=self.styles['Heading1'],
                fontSize=16,
                spaceAfter=20,
                spaceBefore=20,
                textColor=colors.HexColor('#2D3748'),
                fontName='Helvetica-Bold'
            ))
        
        if 'SectionTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SectionTitle',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=10,
                spaceBefore=15,
                textColor=colors.HexColor('#4A5568'),
                fontName='Helvetica-Bold'
            ))
        
        if 'BodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='BodyText',
                parent=self.styles['Normal'],
                fontSize=11,
                spaceAfter=12,
                leading=14,
                textColor=colors.HexColor('#2D3748')
            ))
        
        if 'ImportantText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ImportantText',
                parent=self.styles['Normal'],
                fontSize=12,
                spaceAfter=10,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1A202C')
            ))
    
    def generate_quote_pdf(self, quote_data: dict) -> bytes:
        """
        Génère un PDF de demande de devis
        """
        try:
            logger.info("Début génération PDF devis")
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=inch,
                leftMargin=inch,
                topMargin=inch,
                bottomMargin=inch
            )
            
            # Construire le contenu
            story = []
            
            # En-tête avec logo (si disponible)
            self._add_header(story, quote_data)
            
            # Titre principal
            story.append(Paragraph("DEMANDE DE DEVIS", self.styles['MainTitle']))
            story.append(Spacer(1, 20))
            
            # Informations générales
            self._add_general_info(story, quote_data)
            
            # Informations client
            self._add_client_info(story, quote_data)
            
            # Informations prestataire
            self._add_provider_info(story, quote_data)
            
            # Description des travaux
            self._add_work_description(story, quote_data)
            
            # Pied de page avec instructions
            self._add_footer_instructions(story)
            
            # Générer le PDF
            doc.build(story)
            buffer.seek(0)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"PDF généré avec succès ({len(pdf_bytes)} bytes)")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Erreur génération PDF: {e}")
            raise Exception(f"Impossible de générer le PDF: {str(e)}")
    
    def _add_header(self, story, quote_data):
        """Ajoute l'en-tête avec logo AlloBara"""
        # Table pour alignement logo + info
        header_data = [
            ["ALLOBARA", f"Date: {datetime.now().strftime('%d/%m/%Y')}"],
            ["Plateforme de mise en relation", f"Référence: ALB-{quote_data.get('quote_id', '000000')[:6]}"]
        ]
        
        header_table = Table(header_data, colWidths=[3*inch, 2*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 16),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#F78A1C')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 20))
        
        # Ligne de séparation
        line_data = [["" for _ in range(10)]]
        line_table = Table(line_data, colWidths=[0.5*inch]*10)
        line_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 2, colors.HexColor('#F78A1C')),
        ]))
        story.append(line_table)
        story.append(Spacer(1, 20))
    
    def _add_general_info(self, story, quote_data):
        """Ajoute les informations générales"""
        story.append(Paragraph("INFORMATIONS GÉNÉRALES", self.styles['SectionTitle']))
        
        date_str = quote_data.get('request_date', datetime.now()).strftime('%d/%m/%Y à %H:%M')
        
        info_data = [
            ["Date de la demande:", date_str],
            ["Type de service:", quote_data.get('provider_profession', 'Non spécifié')],
            ["Statut:", "En attente de réponse"]
        ]
        
        info_table = Table(info_data, colWidths=[2*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 20))
    
    def _add_client_info(self, story, quote_data):
        """Ajoute les informations du client"""
        story.append(Paragraph("INFORMATIONS CLIENT", self.styles['SectionTitle']))
        
        client_data = [
            ["Nom complet:", f"{quote_data.get('client_first_name', '')} {quote_data.get('client_last_name', '')}"],
            ["Numéro de téléphone:", quote_data.get('client_phone', 'Non fourni')],
        ]
        
        client_table = Table(client_data, colWidths=[2*inch, 3*inch])
        client_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(client_table)
        story.append(Spacer(1, 20))
    
    def _add_provider_info(self, story, quote_data):
        """Ajoute les informations du prestataire"""
        story.append(Paragraph("PRESTATAIRE CONTACTÉ", self.styles['SectionTitle']))
        
        provider_data = [
            ["Nom:", quote_data.get('provider_name', 'Non spécifié')],
            ["Profession:", quote_data.get('provider_profession', 'Non spécifiée')],
            ["Contact:", quote_data.get('provider_phone', 'Non fourni')],
        ]
        
        provider_table = Table(provider_data, colWidths=[2*inch, 3*inch])
        provider_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F7FAFC')),
        ]))
        
        story.append(provider_table)
        story.append(Spacer(1, 20))
    
    def _add_work_description(self, story, quote_data):
        """Ajoute la description des travaux"""
        story.append(Paragraph("DESCRIPTION DES TRAVAUX DEMANDÉS", self.styles['SectionTitle']))
        
        description = quote_data.get('description', 'Aucune description fournie')
        story.append(Paragraph(description, self.styles['BodyText']))
        story.append(Spacer(1, 20))
    
    def _add_footer_instructions(self, story):
        """Ajoute les instructions en pied de page"""
        story.append(Spacer(1, 30))
        
        # Cadre avec instructions
        instructions = """
        <b>PROCHAINES ÉTAPES :</b><br/>
        1. Le prestataire va examiner votre demande<br/>
        2. Il vous contactera directement pour discuter des détails<br/>
        3. Vous pourrez négocier le prix et planifier l'intervention<br/>
        4. Réglez directement avec le prestataire selon vos accords<br/><br/>
        
        <b>IMPORTANT :</b> AlloBara facilite la mise en relation. 
        Les négociations et paiements se font directement entre vous et le prestataire.
        """
        
        story.append(Paragraph(instructions, self.styles['BodyText']))
        
        story.append(Spacer(1, 20))
        
        # Contact AlloBara
        footer = """
        <b>AlloBara</b> - Plateforme de mise en relation<br/>
        Pour toute question : support@allobara.ci<br/>
        www.allobara.ci
        """
        
        footer_style = ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#718096')
        )
        
        story.append(Paragraph(footer, footer_style))

# Instance globale du générateur
pdf_generator = QuotePDFGenerator()

async def generate_quote_pdf(quote_data: dict) -> bytes:
    """
    Fonction wrapper pour générer un PDF de devis
    """
    try:
        return pdf_generator.generate_quote_pdf(quote_data)
    except Exception as e:
        logger.error(f"Erreur génération PDF: {e}")
        raise