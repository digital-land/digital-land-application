/* global accessibleAutocomplete */

import utils from '../utils'

function MultiSelect ($module) {
  this.$module = $module
}

MultiSelect.prototype.init = function (params) {
  // get the original form field that needs to be kept updated
  this.$formGroup = this.$module.querySelector('[data-multi-select="form-group"]')
  this.$input = this.$formGroup.querySelector('input')

  // Setup options first so we can use the field label
  this.setupOptions(params)

  // Initialize currentlySelected array
  this.currentlySelected = []

  // get the options from a hidden select element
  this.$hiddenSelect = this.$module.querySelector('[data-multi-select="select"]')
  this.selectOptions = utils.getSelectOptions(this.$hiddenSelect)
  this.selectOptionLabels = this.selectOptions.map(($option) => $option[0])

  // set up a type ahead component first
  this.setUpTypeAhead()

  // setup area to display selected
  this.setupSelectedPanel()

  // get and display the initial set of selections
  this.initiallySelected()

  // hide the original form element
  this.$formGroup.classList.add(this.options.hiddenClass)

  return this
}

MultiSelect.prototype.autoCompleteOnConfirm = function (inputValue) {
  console.log(inputValue)
  if (inputValue) {
    const option = this.findOption(inputValue, 'name')
    // if matching option
    if (option.length) {
      // check it isn't already selected
      if (!this.currentlySelected.includes(option[0][1])) {
        this.currentlySelected.push(option[0][1])
        // show in selected panel
        this.displaySelectedItem(option[0])
      }
      // update the original input
      this.updateInput()
    }
    // once processed, empty input if option set
    if (this.options.emptyInputOnConfirm) {
      const $typeAheadInput = this.$typeAheadContainer.querySelector('.autocomplete__input')
      // hacky because autocomplete component calls setState after executing callback
      // so need to wait
      setTimeout(function () {
        $typeAheadInput.value = ''
      }, 150)
    }
    console.log(option)
  }
}

MultiSelect.prototype.createSelectedItem = function (optionPair) {
  const $item = document.createElement('li')
  const $content = document.createElement('div')
  const $label = document.createElement('span')
  $label.classList.add('multi-select__item-label')
  $label.textContent = optionPair[0]
  const $val = document.createElement('span')
  $val.classList.add('multi-select__item-value')
  $val.textContent = optionPair[1]

  const $cancelBtn = document.createElement('a')
  $cancelBtn.classList.add('govuk-link')
  $cancelBtn.textContent = 'deselect'
  $cancelBtn.href = '#'
  const boundOnDeselectItem = this.onDeselectItem.bind(this)
  $cancelBtn.addEventListener('click', boundOnDeselectItem)

  $content.appendChild($label)
  $content.appendChild($val)

  $item.appendChild($content)
  $item.appendChild($cancelBtn)
  return $item
}

MultiSelect.prototype.onDeselectItem = function (e) {
  e.preventDefault()
  const $deselectBtn = e.currentTarget
  const $item = $deselectBtn.closest('li')
  const val = $item.querySelector('.multi-select__item-value').textContent
  $item.remove()
  console.log('deselect from input', val)
  this.currentlySelected = this.currentlySelected.filter(item => item !== val)
  this.updateInput()
  this.updatePanelContent()
}

MultiSelect.prototype.displaySelected = function () {
  // Clear any existing content
  while (this.$selectedPanel.firstChild) {
    this.$selectedPanel.removeChild(this.$selectedPanel.firstChild)
  }

  // Display any pre-existing selections
  if (this.currentlySelected.length) {
    this.$selectedPanel.classList.remove('multi-select__select-panel--none')
    this.$selectedPanel.classList.add('multi-select__select-panel--selection')

    const heading = document.createElement('h4')
    heading.className = 'govuk-heading-s'
    heading.textContent = `Selected ${this.options.nameOfThingSelecting}`
    this.$selectedPanel.appendChild(heading)

    const ul = document.createElement('ul')
    this.currentlySelected.forEach(value => {
      const option = this.findOption(value, 'value')
      if (option && option.length) {
        const li = this.createSelectedItem(option[0])
        ul.appendChild(li)
      }
    })
    this.$selectedPanel.appendChild(ul)
  } else {
    this.$selectedPanel.classList.add('multi-select__select-panel--none')
    this.$selectedPanel.classList.remove('multi-select__select-panel--selection')
    const p = document.createElement('p')
    p.className = 'govuk-hint'
    p.textContent = 'No selections made'
    this.$selectedPanel.appendChild(p)
  }
}

MultiSelect.prototype.displaySelectedItem = function (option) {
  if (!this.$selectedPanel) {
    this.setupSelectedPanel()
  }

  // Create list if it doesn't exist
  if (!this.$selectedPanel.querySelector('ul')) {
    const heading = document.createElement('h4')
    heading.className = 'govuk-heading-s'
    heading.textContent = `Selected ${this.options.nameOfThingSelecting}`
    this.$selectedPanel.appendChild(heading)

    const ul = document.createElement('ul')
    this.$selectedPanel.appendChild(ul)
  }

  const ul = this.$selectedPanel.querySelector('ul')
  const li = this.createSelectedItem(option)
  ul.appendChild(li)
  this.updatePanelContent()
}

MultiSelect.prototype.findOption = function (value, type) {
  if (type === 'name') {
    return this.selectOptions.filter(option => option[0].toLowerCase() === value.toLowerCase())
  }
  return this.selectOptions.filter(option => option[1] === value)
}

MultiSelect.prototype.getSelectionsFromString = function (str) {
  const selections = str.split(this.options.separator)
  return selections.filter(s => s !== '')
}

MultiSelect.prototype.initAccessibleAutocomplete = function ($container) {
  const boundAutoCompleteOnConfirm = this.autoCompleteOnConfirm.bind(this)
  console.log('setup', this.selectOptionList)
  accessibleAutocomplete({
    element: $container.querySelector('.autocomplete-container'),
    id: $container.querySelector('label').htmlFor, // To match it to the existing <label>.
    source: this.selectOptionLabels,
    showNoOptionsFound: false,
    onConfirm: boundAutoCompleteOnConfirm
  })
}

MultiSelect.prototype.initiallySelected = function () {
  // Get the value from the input's value attribute, not its current value
  const inputString = this.$input.getAttribute('value') || this.$input.value || ''
  if (inputString) {
    this.currentlySelected = this.getSelectionsFromString(inputString)
    // Panel should already exist at this point
    this.displaySelected()
  }
}

MultiSelect.prototype.setupSelectedPanel = function () {
  // Create the panel if it doesn't exist
  if (!this.$selectedPanel) {
    this.$selectedPanel = document.createElement('div')
    this.$selectedPanel.className = 'multi-select__select-panel multi-select__select-panel--none'
    // Insert after the typeahead container
    this.$typeAheadContainer.parentNode.insertBefore(this.$selectedPanel, this.$typeAheadContainer.nextSibling)
  }
  // Initialize with empty state
  const p = document.createElement('p')
  p.className = 'govuk-hint'
  p.textContent = 'No selections made'
  this.$selectedPanel.appendChild(p)
}

MultiSelect.prototype.setUpTypeAhead = function () {
  const labelText = this.$formGroup.querySelector('label').textContent
  const hintText = this.$input.dataset.hint || 'Start typing to see suggestions'
  this.$typeAheadContainer = utils.createTypeAheadContainer(labelText, this.$hiddenSelect.id, hintText)
  this.$module.append(this.$typeAheadContainer)

  this.initAccessibleAutocomplete(this.$typeAheadContainer)
}

// this keeps the hidden input updated
MultiSelect.prototype.updateInput = function () {
  this.$input.value = this.currentlySelected.join(this.options.separator)
}

MultiSelect.prototype.updatePanelContent = function () {
  // Ensure currentlySelected exists
  if (!this.currentlySelected) {
    this.currentlySelected = []
  }

  // if no items selected then show no selection msg
  if (this.currentlySelected.length > 0) {
    this.$selectedPanel.classList.remove('multi-select__select-panel--none')
    this.$selectedPanel.classList.add('multi-select__select-panel--selection')
  } else {
    this.$selectedPanel.classList.add('multi-select__select-panel--none')
    this.$selectedPanel.classList.remove('multi-select__select-panel--selection')
  }
}

MultiSelect.prototype.setupOptions = function (params) {
  params = params || {}
  this.options = {}
  this.options.separator = params.separator || ';'

  // Get the field label text to use as the name of thing being selected
  const fieldLabel = this.$formGroup.querySelector('label').textContent.toLowerCase()
  this.options.nameOfThingSelecting = params.nameOfThingSelecting || fieldLabel || 'items'

  this.options.hiddenClass = params.hiddenClass || 'app-hidden'
  this.options.emptyInputOnConfirm = params.emptyInputOnConfirm || true
}

export default MultiSelect
