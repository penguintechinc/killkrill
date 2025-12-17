import { Tab } from '@headlessui/react';
import PropTypes from 'prop-types';

const TabContainer = ({ tabs, defaultIndex = 0 }) => {
  return (
    <div className="w-full">
      <Tab.Group defaultIndex={defaultIndex}>
        <Tab.List className="flex border-b border-gray-300 bg-gray-900">
          {tabs.map((tab) => (
            <Tab
              key={tab.id}
              className={({ selected }) =>
                `px-6 py-3 text-sm font-medium focus:outline-none transition-colors ${
                  selected
                    ? 'text-yellow-500 border-b-2 border-yellow-500'
                    : 'text-gray-400 hover:text-gray-200'
                }`
              }
            >
              {tab.label}
            </Tab>
          ))}
        </Tab.List>
        <Tab.Panels className="bg-gray-800 rounded-b-lg">
          {tabs.map((tab) => (
            <Tab.Panel key={tab.id} className="p-6">
              {tab.content}
            </Tab.Panel>
          ))}
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
};

TabContainer.propTypes = {
  tabs: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
      content: PropTypes.node.isRequired,
    })
  ).isRequired,
  defaultIndex: PropTypes.number,
};

export default TabContainer;
