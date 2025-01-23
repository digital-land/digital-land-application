/* global fetch, turf */
import SelectOrNew from './modules/select-or-new'
import MultiSelect from './modules/multi-select'
import Slugify from './modules/slugify'

function getBoundingBox(features, units) {
  const _units = units || 1

  // check if features param is already a FeatureCollection
  let collection = features
  if (!Object.prototype.hasOwnProperty.call(features, 'type') || features.type !== 'FeatureCollection') {
    collection = turf.featureCollection(features)
  }

  const bufferedCollection = turf.buffer(collection, _units)
  const envelope = turf.envelope(bufferedCollection)
  return envelope.bbox
}

window.dptp = {
  getBoundingBox: getBoundingBox,
  MultiSelect: MultiSelect,
  SelectOrNew: SelectOrNew,
  Slugify: Slugify
}
