# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

import warnings

from .address import PostalAddress, compat_field
from .base import (
    Capability, BaseObject, DecimalField, StringField, UserError, Field,
    DeprecatedFieldWarning,
)
from .date import DateField

__all__ = ['Profile', 'Person', 'Company', 'CapProfile']


class ProfileMissing(UserError):
    """
    Raised when profile is not accessible
    """


class Profile(BaseObject):
    """
    Profile.
    """
    name =                        StringField('Full name or company name')
    postal_address =              Field('Postal address', PostalAddress)
    phone =                       StringField('Phone number')
    professional_phone =          StringField('Professional phone number')
    email =                       StringField('EMail address')
    professional_email =          StringField('Professional email')
    main_bank =                   StringField('Main bank')

    address = compat_field('postal_address', 'full_address')
    country = compat_field('postal_address', 'country')


class Company(Profile):
    """
    Company.
    """
    siren = StringField('French SIREN Number')
    registration_date = DateField('Registration date')
    activity_area = StringField('Activity area')


class Person(Profile):
    """
    Person.
    """
    birth_date =                  DateField('Birth date')
    firstname =                   StringField("Person's firstname")
    lastname =                    StringField("Person's lastname")
    nationality =                 StringField('Nationality of person')
    mobile =                      StringField('Mobile number of person')
    gender =                      StringField('Gender of person')
    birth_name =                  StringField('Birth name')
    spouse_name =                 StringField('Name of spouse')
    children =                    DecimalField('Number of children')
    family_situation =            StringField('Family situation')
    matrimonial =                 StringField('Matrimonial status')
    housing_status =              StringField('Housing status')
    job =                         StringField('Profession')
    job_start_date =              DateField('Start date of current job')
    job_contract_type =           StringField('Contract type of current job')
    company =                     Field("Company of current job", Company)
    socioprofessional_category =  StringField('Socio-Professional Category')

    job_activity_area = compat_field("company", "activity_area")
    company_name = compat_field("company", "name")
    company_siren = compat_field("company", "siren")

    @property
    def maiden_name(self):
        warnings.warn(
            'Field is deprecated, use .birth_name field instead.',
            DeprecatedFieldWarning, stacklevel=3,
        )
        return self.birth_name

    @maiden_name.setter
    def maiden_name(self, value):
        warnings.warn(
            'Field is deprecated, use .birth_name field instead.',
            DeprecatedFieldWarning, stacklevel=3,
        )
        self.birth_name = value


class GlobalProfileNotImplementedError(NotImplementedError):
    """
    It allows to use the CapProfile for accounts with AccountOwnerProfile
    """
    pass


class CapProfile(Capability):
    def get_profile(self):
        """
        Get profile.

        :rtype: :class:`Person` or :class:`Company`
        """
        raise NotImplementedError()
