from flask import Flask, render_template
from flask_wtf import FlaskForm
from wtforms import SubmitField, IntegerField
from wtforms.validators import DataRequired, NumberRange
import math


class Form(FlaskForm):
    heater_power = IntegerField("Heater power", validators=[DataRequired(), NumberRange(min=0)],
                                description="Unit: Watts", default="7000")

    aircon_power = IntegerField("Air conditioner power", validators=[DataRequired(), NumberRange(min=0)],
                                description="Unit: Watts", default="7000")

    humidifier_power = IntegerField("Humidifier power", validators=[DataRequired(), NumberRange(min=0)],
                                    description="Unit: Kilograms of water per hour", default="4")

    dehumidifier_power = IntegerField("Dehumidifier power", validators=[DataRequired(), NumberRange(min=0)],
                                      description="Unit: Kilograms of water per hour", default="4")

    room_width = IntegerField("Room width", validators=[DataRequired(), NumberRange(min=0)],
                              description="Unit: Meters", default="10")

    room_height = IntegerField("Room height", validators=[DataRequired(), NumberRange(min=0)],
                               description="Unit: Meters", default="10")

    room_length = IntegerField("Room length", validators=[DataRequired(), NumberRange(min=0)],
                               description="Unit: Meters", default="10")

    air_change = IntegerField("Air change", validators=[DataRequired(), NumberRange(min=0, max=100)],
                              description="Unit: Percent. Describes what percentage of the rooms' air "
                                          "will be changed within an hour.", default="30")

    T = IntegerField("Simulation interval", validators=[DataRequired(), NumberRange(min=0)],
                     description="Unit: Seconds", default="10")

    t_sim = IntegerField("Simulation time", validators=[DataRequired(), NumberRange(min=0)],
                         description="Unit: Hours", default="12")

    outside_temp = IntegerField("Outside temperature", validators=[DataRequired(), NumberRange(min=-25, max=40)],
                                description="Unit: Celsius", default="-20")

    outside_relative_humidity = IntegerField("Outside relative humidity", validators=[NumberRange(min=0, max=100)],
                                             description="Unit: Percent", default="0")

    temp_set = IntegerField("Sought temperature", validators=[DataRequired(), NumberRange(min=-25, max=40)],
                            description="Unit: Celsius", default="35")

    relative_humidity_set = IntegerField("Sought relative humidity", validators=[NumberRange(min=0, max=100)],
                                         description="Unit: Percent", default="45")

    temp = IntegerField("Current room temperature", validators=[DataRequired(), NumberRange(min=-25, max=40)],
                        description="Unit: Celsius", default="-15")

    relative_humidity = IntegerField("Current room relative humidity",
                                     validators=[NumberRange(min=0, max=100)],
                                     description="Unit: Percent", default="40")

    submit = SubmitField('Simulate', description="")


class RR:
    # constants:
    overall_press = 101325  # Pa
    K = 273.15  # C
    water_vapor_mol_mass = 0.018016  # kg/mol
    air_mol_mass = 0.02897  # average kg/mol
    dry_air_gas_const = 287.058  # J/(kg*K)
    vapor_gas_const = 461.495  # J/(kg*K)

    @staticmethod
    def main(form):
        # variables set by user:
        heater_power = form.heater_power.data
        aircon_power = form.aircon_power.data
        humidifier_power = form.humidifier_power.data / 3600
        dehumidifier_power = form.dehumidifier_power.data / 3600
        room_width = form.room_width.data
        room_height = form.room_height.data
        room_length = form.room_length.data
        air_change = form.air_change.data/(100*3600)
        t = form.T.data
        t_sim = form.t_sim.data * 3600

        outside_temp = form.outside_temp.data
        outside_relative_humidity = form.outside_relative_humidity.data/100

        temp_set = form.temp_set.data
        relative_humidity_set = form.relative_humidity_set.data/100

        temp = [form.temp.data]
        relative_humidity = [form.relative_humidity.data/100]

        # variables calculated from users input:
        # room:
        room_cap = room_width * room_height * room_length  # m^3
        n = math.ceil(t_sim / t)  # dimensionless

        # sought values:
        absolute_humidity_set = RR.relative2absolute_humidity(temp_set, relative_humidity_set)  # kg/m^3
        air_den_set = RR.air_density(temp_set, relative_humidity_set)  # kg/m^3
        air_heat_capacity_set = RR.air_heat_capacity(temp_set, absolute_humidity_set, air_den_set)  # J/(kg*K)
        air_energy_set = air_den_set * temp_set * air_heat_capacity_set  # J

        # beginning values:
        absolute_humidity = [RR.relative2absolute_humidity(temp[-1], relative_humidity[-1])]  # kg/m^3

        # outside values:
        outside_absolute_humidity = RR.relative2absolute_humidity(outside_temp, outside_relative_humidity)  # kg/m^3
        outside_air_den = RR.air_density(outside_temp, outside_relative_humidity)  # kg/m^3
        heat_outside = round(outside_air_den * outside_temp * air_change * t, 6)  # kg*C

        # program:
        for i in range(0, n):
            # calculating values of variables needed for calculation:
            air_den = RR.air_density(temp[-1], relative_humidity[-1])
            current_air_heat_capacity = RR.air_heat_capacity(temp[-1], absolute_humidity[-1], air_den)

            # calculating needed temperature changes:
            needed_heat = round((air_energy_set - air_den * temp[-1] * current_air_heat_capacity) * room_cap, 6)
            if needed_heat > 0:
                heat_change = RR.added(needed_heat, (heater_power * t))
            else:
                heat_change = -RR.added(-needed_heat, (aircon_power * t))

            # calculating needed humidity changes:
            absolute_humidity_set = RR.relative2absolute_humidity(temp[-1], relative_humidity_set)
            needed_water = round((absolute_humidity_set - absolute_humidity[-1]) * room_cap, 9)
            if needed_water >= 0:
                water_change = RR.added(needed_water, (humidifier_power * t))
            else:
                water_change = -RR.added(-needed_water, (dehumidifier_power * t))

            # applying results:
            temp.append(temp[-1] + heat_change / (air_den * room_cap * current_air_heat_capacity))
            absolute_humidity.append((absolute_humidity[-1] * room_cap + water_change) / room_cap)
            relative_humidity.append(RR.absolute2relative_humidity(temp[-1], absolute_humidity[-1]))

            # ventilation:
            heat_current = round(air_den * temp[-1] * (1 - air_change * t), 6)
            temp[-1] = (heat_current + heat_outside) /\
                       ((1 - air_change * t) * air_den + air_change * t * outside_air_den)

            absolute_humidity[-1] = round(absolute_humidity[-1] * (1 - air_change * t)
                                          + outside_absolute_humidity * air_change * t, 9)

            relative_humidity[-1] = RR.absolute2relative_humidity(temp[-1], absolute_humidity[-1])

            # moderating relative humidity:
            if relative_humidity[-1] > 1:
                relative_humidity[-1] = 1
                absolute_humidity[-1] = RR.relative2absolute_humidity(temp[-1], relative_humidity[-1])

        # formatting results:
        axis_x = range(0, n + 1)
        axis_x = [str(math.floor(x * t / 3600)) + ':'
                  + str(round((x * t / 3600 - math.floor(x * t / 3600))*60)).rjust(2, '0') for x in axis_x]
        relative_humidity_perc = [100 * x for x in relative_humidity]

        return [axis_x, temp, relative_humidity_perc]

    @staticmethod
    def relative2absolute_humidity(temp, relative_humidity):
        # changes given relative humidity into absolute humidity values
        return 6.112 * math.e ** (17.67 * temp / (temp + 243.5)) * relative_humidity * 2.1674 / (10 * (RR.K + temp))
        # kg/m^3

    @staticmethod
    def absolute2relative_humidity(temp, absolute_humidity):
        # changes given absolute humidity into relative humidity values
        q = absolute_humidity / (100 * (RR.overall_press / (287.058 * (temp + RR.K)) + absolute_humidity))
        relative_humidity = 0.263 * RR.overall_press * q * 1 / math.exp(17.67 * temp / (temp - 29.65 + RR.K))
        return math.ceil(relative_humidity * 100) / 100  # %

    @staticmethod
    def air_heat_capacity(temp, absolute_humidity, air_den):
        # calculates air heat capacity
        air_moles = (air_den - absolute_humidity) / RR.air_mol_mass
        water_vapor_moles = absolute_humidity / RR.water_vapor_mol_mass
        xw = water_vapor_moles / (water_vapor_moles + air_moles)

        cpa = 0.251625 - (9.2525 * 10 ** (-5)) * (temp + RR.K) + (2.1334 * 10 ** (-7)) * (temp + RR.K) ** 2 - (
                1.0043 * 10 ** (-10)) * (temp + RR.K) ** 3
        cpw = 0.452219 - (1.29224 * 10 ** (-4)) * (temp + RR.K) + (4.17008 * 10 ** (-7)) * (temp + RR.K) ** 2 - (
                2.00401 * 10 ** (-10)) * (temp + RR.K) ** 3

        return (cpa + xw * (0.622 * cpw - cpa)) / (1 - 0.378 * xw) * 1000 * 4.184  # J/(kg*K)

    @staticmethod
    def air_density(temp, relative_humidity):
        # calculates air density
        vapor_press = 100 * relative_humidity * 6.1078 * 10 ** (7.5 * temp / (temp + 237.3))  # Pa
        dry_air_press = RR.overall_press - vapor_press  # Pa
        return (dry_air_press / (RR.dry_air_gas_const * (RR.K + temp))) + (
                vapor_press / (RR.vapor_gas_const * (RR.K + temp)))  # kg/m^3

    @staticmethod
    def added(needed, maximum):
        # calculates how much water/heat can be added to the system in given time period
        if needed / maximum >= 1:
            return round(maximum, 9)
        elif needed > 0:
            return round(needed, 9)
        else:
            return 0


app = Flask(__name__)
app.config['SECRET_KEY'] = 'you-will-never-guess'


@app.route('/', methods=['GET', 'POST'])
def home():
    form = Form()
    if form.validate_on_submit():
        axis_x, temp, relative_humidity_perc = RR.main(form)
        return render_template("chart.html", labels=axis_x, temp=temp, relative_humidity_perc=relative_humidity_perc)

    return render_template("home.html", form=form)


if __name__ == '__main__':
    app.run(debug=False)
