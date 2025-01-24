/* global fetch */

const utils = {}


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
