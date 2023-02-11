# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from woob.capabilities.housing import POSTS_TYPES, HOUSE_TYPES

TRANSACTION_TYPE = {
    POSTS_TYPES.SALE: 'buy',
    POSTS_TYPES.RENT: 'rent',
    POSTS_TYPES.VIAGER: 'buy',
    POSTS_TYPES.FURNISHED_RENT: 'rent',
}


HOUSE_TYPES_LABELS = {
    HOUSE_TYPES.APART: ['flat'],
    HOUSE_TYPES.HOUSE: ['house'],
    HOUSE_TYPES.PARKING: ['parking'],
    HOUSE_TYPES.LAND: ['terrain'],
    HOUSE_TYPES.OTHER: ['others', 'loft', 'shop', 'building', 'castle', 'premises', 'office', 'townhouse'],
    HOUSE_TYPES.UNKNOWN: []
}
