from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, FloatField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class StrategyForm(FlaskForm):
    name = StringField('Strategy Name', 
                       validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', 
                              validators=[Optional(), Length(max=500)])
    code = TextAreaField('Strategy Code') 
    submit = SubmitField('Save Strategy')

class StrategyInstanceForm(FlaskForm):
    name = StringField('Instance Name', 
                       validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', 
                              validators=[Optional(), Length(max=500)])
    
    # Instrument settings
    symbol = StringField('Symbol', 
                        validators=[DataRequired(), Length(min=1, max=20)])
    exchange = SelectField('Exchange', 
                          choices=[('NSE', 'NSE'), ('BSE', 'BSE'), ('NFO', 'NFO'), ('CDS', 'CDS')],
                          validators=[DataRequired()])
    timeframe = SelectField('Timeframe', 
                          choices=[
                              ('1m', '1 Minute'), 
                              ('5m', '5 Minutes'), 
                              ('15m', '15 Minutes'), 
                              ('30m', '30 Minutes'),
                              ('60m', '1 Hour'),
                              ('D', 'Daily')
                          ],
                          validators=[DataRequired()])
    
    # Signal actions
    long_entry_action = TextAreaField('Long Entry Action', 
                                   validators=[Optional(), Length(max=500)])
    long_exit_action = TextAreaField('Long Exit Action', 
                                  validators=[Optional(), Length(max=500)])
    short_entry_action = TextAreaField('Short Entry Action', 
                                    validators=[Optional(), Length(max=500)])
    short_exit_action = TextAreaField('Short Exit Action', 
                                   validators=[Optional(), Length(max=500)])
    
    # Position sizing and risk management
    position_size = FloatField('Position Size (in %)', 
                              validators=[Optional(), NumberRange(min=0.1, max=100)])
    intraday = BooleanField('Intraday Strategy', default=True)
    
    submit = SubmitField('Save Instance')
