/* global fetch */

const utils = {}

utils.createTypeAheadContainer = function (labelText, id, hintText) {
  const $container = document.createElement('div')
  $container.classList.add('govuk-form-group')

  const $label = document.createElement('label')
  $label.classList.add('govuk-label')
  $label.setAttribute('for', id + '-typeAhead')
  $label.textContent = labelText

  if (hintText) {
    const $hint = document.createElement('div')
    $hint.classList.add('govuk-hint')
    $hint.textContent = hintText
    $container.appendChild($hint)
  }

  const $autocompleteContainer = document.createElement('div')
  $autocompleteContainer.classList.add('autocomplete-container')

  $container.appendChild($label)
  $container.appendChild($autocompleteContainer)

  return $container
}

utils.getSelectOptions = function ($select) {
  const $options = $select.querySelectorAll('option')
  return Array.from($options).map(($option) => [$option.textContent, $option.value])
}

utils.postRecordToRegister = function (url, data, onSuccess, onError) {
  fetch(url, {
    method: 'POST',
    body: JSON.stringify(data),
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      if (onSuccess) {
        onSuccess(data)
      } else {
        console.log('Success:', data)
      }
    })
    .catch((error) => {
      if (onError) {
        onError(error)
      } else {
        console.error('Error:', error)
      }
    })
}

export default utils
